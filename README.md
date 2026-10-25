# cnlab
SDN-based dynamic host blocking: detects abnormal TCP traffic with Ryu + Mininet and installs OpenFlow drop rules automatically.
Addresses: h1 server 10.0.0.1, h2/h3 clients, h4 attacker 10.0.0.4.
Port: TCP 5000.
Client output: timestamp,rtt_ms,status, with timestamp as an epoch time.
Attacker output: ATTACK START t=<epoch> and FIRST FAILURE t=<epoch>.
Controller log: events.csv with columns epoch,time,event,ip,detail.
