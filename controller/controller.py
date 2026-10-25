#!/usr/bin/env python3
"""Ryu app: learning switch + dynamic host blocking.

Detection:
  1. Connection rate: counts TCP SYNs per source IP in a sliding window (via packet_in,
     because every new TCP connection becomes a new flow).
  2. Packet rate: polls flow statistics and computes packets/sec per source IP.
Response:
  Installs a high-priority DROP rule for the offending source IP with a hard_timeout,
  so the host is automatically unblocked (recovery) when the timer expires.

Run:  ryu-manager controller.py
"""
import csv
import time
from collections import defaultdict, deque

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, tcp
from ryu.ofproto import ofproto_v1_3

# ---------------- configurable thresholds ----------------
SYN_THRESHOLD = 15      # SYNs from one IP inside WINDOW seconds => suspicious
WINDOW = 5              # seconds
PPS_THRESHOLD = 1500    # packets/sec from one IP (from flow stats) => suspicious
BLOCK_TIME = 30         # seconds before the host is automatically unblocked
STATS_INTERVAL = 2      # seconds between flow-stats polls
WHITELIST = {'10.0.0.1'}  # never block the server
EVENT_LOG = 'events.csv'

PRIO_FLOW, PRIO_BLOCK = 10, 100


class HostBlocker(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.syns = defaultdict(deque)   # ip -> timestamps of recent SYNs
        self.blocked = {}                # ip -> time blocked
        self.prev_pkts = {}              # flow key -> last packet count
        self.log_file = open(EVENT_LOG, 'a', newline='')
        self.csv = csv.writer(self.log_file)
        hub.spawn(self._monitor)

    # ---------- logging ----------
    def log_event(self, event, ip, detail=''):
        row = [f"{time.time():.3f}", time.strftime('%H:%M:%S'), event, ip, detail]
        self.csv.writerow(row)
        self.log_file.flush()
        self.logger.info("%s %s %s", event, ip, detail)

    # ---------- switch setup ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        self.datapaths[dp.id] = dp
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)  # table-miss

    def add_flow(self, dp, priority, match, actions, idle=0, hard=0, flags=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                      instructions=inst, idle_timeout=idle,
                                      hard_timeout=hard, flags=flags))

    # ---------- packet handling ----------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out_port = self.mac_to_port[dp.id].get(eth.dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        ip = pkt.get_protocol(ipv4.ipv4)
        t = pkt.get_protocol(tcp.tcp)
        if ip and t:
            is_syn = (t.bits & tcp.TCP_SYN) and not (t.bits & tcp.TCP_ACK)
            if is_syn and self.record_syn(ip.src):
                return  # host is blocked / just got blocked: drop this packet
            if out_port != ofp.OFPP_FLOOD:
                match = parser.OFPMatch(eth_type=0x0800, ip_proto=6,
                                        ipv4_src=ip.src, ipv4_dst=ip.dst,
                                        tcp_src=t.src_port, tcp_dst=t.dst_port)
                self.add_flow(dp, PRIO_FLOW, match, actions, idle=10)

        dp.send_msg(parser.OFPPacketOut(datapath=dp, buffer_id=ofp.OFP_NO_BUFFER,
                                        in_port=in_port, actions=actions, data=msg.data))

    # ---------- detection ----------
    def record_syn(self, src_ip):
        """Returns True if this SYN should be dropped."""
        if src_ip in self.blocked:
            return True
        if src_ip in WHITELIST:
            return False
        now = time.time()
        q = self.syns[src_ip]
        q.append(now)
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= SYN_THRESHOLD:
            self.block_host(src_ip, f"{len(q)} SYNs in {WINDOW}s "
                                    f"(first seen {now - q[0]:.2f}s ago)")
            return True
        return False

    def block_host(self, ip, reason):
        if ip in self.blocked:
            return
        self.blocked[ip] = time.time()
        self.log_event('BLOCKED', ip, reason)
        for dp in self.datapaths.values():
            parser, ofp = dp.ofproto_parser, dp.ofproto
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip)
            self.add_flow(dp, PRIO_BLOCK, match, [], hard=BLOCK_TIME,
                          flags=ofp.OFPFF_SEND_FLOW_REM)  # empty actions = drop

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed(self, ev):
        msg = ev.msg
        if msg.priority == PRIO_BLOCK:
            ip = msg.match.get('ipv4_src')
            self.blocked.pop(ip, None)
            self.syns[ip].clear()
            self.log_event('UNBLOCKED', ip, 'block timer expired (recovery)')

    # ---------- flow statistics ----------
    def _monitor(self):
        while True:
            hub.sleep(STATS_INTERVAL)
            for dp in list(self.datapaths.values()):
                dp.send_msg(dp.ofproto_parser.OFPFlowStatsRequest(dp))

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats_reply(self, ev):
        per_ip = defaultdict(int)
        for st in ev.msg.body:
            if st.priority != PRIO_FLOW:
                continue
            m = st.match
            src = m.get('ipv4_src')
            if src is None:
                continue
            key = (src, m.get('ipv4_dst'), m.get('tcp_src'), m.get('tcp_dst'))
            delta = st.packet_count - self.prev_pkts.get(key, 0)
            if delta < 0:
                delta = st.packet_count
            self.prev_pkts[key] = st.packet_count
            per_ip[src] += delta
        for ip, pkts in per_ip.items():
            pps = pkts / STATS_INTERVAL
            if pps > 0:
                self.logger.info("STATS %s %.0f pkts/s", ip, pps)
            if ip not in WHITELIST and pps > PPS_THRESHOLD:
                self.block_host(ip, f"{pps:.0f} pkts/s > {PPS_THRESHOLD}")
