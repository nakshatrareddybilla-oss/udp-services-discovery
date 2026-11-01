import os
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, udp
from ryu.lib import hub

ALLOWED_UDP = {5000, 6000, 6001}     # discovery + service ports
BLOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocked.txt")


class ServiceSDN(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.mac_to_port = {}
        self.datapaths = {}
        self.blocked = set()
        hub.spawn(self.watch_block_file)

    # ---------- helpers ----------
    def add_flow(self, dp, prio, match, actions, idle=0):
        p, o = dp.ofproto_parser, dp.ofproto
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match,
                                 instructions=inst, idle_timeout=idle))

    def block_ip(self, dp, ip):
        p = dp.ofproto_parser
        for field in ("ipv4_src", "ipv4_dst"):
            m = p.OFPMatch(eth_type=0x0800, **{field: ip})
            self.add_flow(dp, 10, m, [])            # no actions = drop
        self.logger.info("BLOCK host %s (drop rules installed)", ip)

    def unblock_ip(self, dp, ip):
        p, o = dp.ofproto_parser, dp.ofproto
        for field in ("ipv4_src", "ipv4_dst"):
            m = p.OFPMatch(eth_type=0x0800, **{field: ip})
            dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE_STRICT,
                                     priority=10, match=m,
                                     out_port=o.OFPP_ANY, out_group=o.OFPG_ANY))
        self.logger.info("UNBLOCK host %s (drop rules removed)", ip)

    def watch_block_file(self):
        # every second, read blocked.txt and apply changes live
        while True:
            hub.sleep(1)
            try:
                with open(BLOCK_FILE) as f:
                    new = {l.strip() for l in f if l.strip()}
            except OSError:
                new = set()
            for ip in new - self.blocked:
                for dp in self.datapaths.values():
                    self.block_ip(dp, ip)
            for ip in self.blocked - new:
                for dp in self.datapaths.values():
                    self.unblock_ip(dp, ip)
            self.blocked = new

    # ---------- switch connects ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        self.datapaths[dp.id] = dp
        # table-miss: unknown packets go to the controller
        self.add_flow(dp, 0, p.OFPMatch(),
                      [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])
        for ip in self.blocked:
            self.block_ip(dp, ip)

    # ---------- packets that have no flow rule yet ----------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp, o, p = msg.datapath, msg.datapath.ofproto, msg.datapath.ofproto_parser
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        ip = pkt.get_protocol(ipv4.ipv4)
        u = pkt.get_protocol(udp.udp)

        # policy: only discovery/service UDP ports are allowed
        if u and u.dst_port not in ALLOWED_UDP and u.src_port not in ALLOWED_UDP:
            self.logger.info("DROP unknown UDP port %s: %s -> %s",
                             u.dst_port, ip.src, ip.dst)
            return
        if u:
            self.logger.info("SERVICE TRAFFIC %s:%s -> %s:%s",
                             ip.src, u.src_port, ip.dst, u.dst_port)

        # learning switch
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD)
        actions = [p.OFPActionOutput(out)]

        # install a fast-path rule so later packets skip the controller
        if out != o.OFPP_FLOOD and u:
            m = p.OFPMatch(in_port=in_port, eth_src=eth.src, eth_dst=eth.dst,
                           eth_type=0x0800, ip_proto=17,
                           udp_src=u.src_port, udp_dst=u.dst_port)
            self.add_flow(dp, 5, m, actions, idle=20)

        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                   in_port=in_port, actions=actions, data=data))
