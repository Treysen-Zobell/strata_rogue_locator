from pydash.objects import get
import coloredlogs
import xmltodict
import requests
import logging
import random
import json


class CMSClient:
    def __init__(self, username: str, password: str, node_ip: str, target_platform: str = "e7", logging_level: str = "ERROR"):
        self.logger = logging.getLogger(__name__)
        coloredlogs.install(level=logging_level, logger=self.logger)

        self.uri_extensions = {
            "e7": "/cmsexc/ex/netconf",
            "c7/e3/e5-100": "/cmsweb/nc",
            "ae_ont": "cmsae/ae/netconf"
        }
        if target_platform in self.uri_extensions:
            uri = self.uri_extensions[target_platform]
        else:
            self.logger.debug(f"Invalid target platform {target_platform}, defaulting to e7")
            uri = self.uri_extensions["e7"]

        self.netconf_url = f"http://{node_ip}:18080{uri}"
        self.username = username
        self.node_ip = node_ip
        self.session_id = self.login(username, password)

    def login(self, username: str, password: str):
        """
        Sends a login request to the cms server and returns the session id if successful
        :param username: cms username
        :param password: cms password
        :return: session_id(str) or None
        """
        self.logger.debug("Logging into CMS")
        payload = f"""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
                    <soapenv:Body>
                    <auth message-id="{self.message_id}">
                        <login>
                            <UserName>{username}</UserName>
                            <Password>{password}</Password>
                        </login>
                    </auth>
                    </soapenv:Body>
                    </soapenv:Envelope>"""

        resp = self.__post(payload)
        if resp is None:
            return None
        code = get(resp, "Envelope.Body.auth-reply.ResultCode")
        session_id = get(resp, "Envelope.Body.auth-reply.SessionId")

        if session_id is None or code != "0":
            self.logger.critical("CMS login request failed")
            self.logger.critical(resp)
            return None

        return session_id

    def logout(self):
        """
        Sends a logout request to the CMS server
        :return:
        """
        self.logger.debug("Logging out of CMS")
        payload = f"""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
                    <soapenv:Body>
                    <auth message-id="{self.message_id}">
                        <logout>
                            <UserName>{self.username}</UserName>
                            <SessionId>{self.session_id}</SessionId>
                        </logout>
                    </auth>
                    </soapenv:Body>
                    </soapenv:Envelope>"""

        resp = self.__post(payload)
        if resp is None:
            return None

        self.logger.debug(resp)
        code = get(resp, "Envelope.Body.auth-reply.ResultCode")
        if code != "0":
            self.logger.critical("CMS logout request failed")
            self.logger.critical(resp)

    def get_fiber_info(self, node_id: str, ont_id: str):
        """
        Returns a dict of information about a fiber connection, each key pair could be str: str or str: None
        :param node_id: ex: rsvt-pon-1
        :param ont_id: ex: 18330
        :return:
        """
        self.logger.debug(f"Retrieving info for {ont_id} on {node_id}")
        info = {}

        # request #1
        payload = f"""
                            <soapenv:Envelope xmlns:soapenv="www.w3.org/2003/05/soap-envelope">
                            <soapenv:Body>
                            <rpc message-id="{self.message_id}" nodename="NTWK-{node_id}" username="{self.username}" sessionid="{self.session_id}">
                            <get-config>
                                <source>
                                    <running/>
                                </source>
                                <filter type="subtree">
                                    <top>
                                        <object>
                                        <type>Ont</type>
                                        <id>
                                            <ont>{ont_id}</ont>
                                        </id>
                                        </object>
                                    </top>
                                </filter>
                            </get-config>
                            </rpc>
                            </soapenv:Body>
                            </soapenv:Envelope>"""

        resp = self.__post(payload)
        if resp is None:
            self.logger.error(f"Failed to pull info for {ont_id} on {node_id}")
            return {}

        self.logger.debug(resp)
        info["serial_nr"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.data.top.object.serno")
        info["admin_state"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.data.top.object.admin")

        # request #2
        payload = f"""
                    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
                    <soapenv:Body>
                        <rpc message-id="1" nodename="NTWK-{node_id}" username="{self.username}" sessionid="{self.session_id}">
                        <action>
                            <action-type>show-ont</action-type>
                            <action-args><serno>{info["serial_nr"]}</serno></action-args>
                        </action>
                    </rpc>
                    </soapenv:Body>
                    </soapenv:Envelope>"""

        resp = self.__post(payload)
        if resp is None:
            self.logger.error(f"Failed to pull ont info for CXNK-{info['serial_nr']} on {node_id}")
            return {}

        self.logger.debug(resp)
        info["model"] = get(resp,
                            "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get-config.object.ontprof.id.ontprof.@name")
        info["optical_transmit"] = get(resp,
                                       "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.opt-sig-lvl")
        info["optical_receive"] = get(resp,
                                      "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.fe-opt-lvl")
        info["major_alarms"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.maj")
        info["minor_alarms"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.min")
        info["warning_alarms"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.warn")
        info["info_alarms"] = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.match.get.object.info")

        # request #3
        payload = f"""
                            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
                            <soapenv:Body>
                            <rpc message-id="1" nodename="NTWK-{node_id}" username="{self.username}" sessionid="{self.session_id}">
                            <action>
                                <action-type>show-ont-pm</action-type>
                                <action-args>
                                    <object>
                                        <type>Ont</type>
                                        <id>
                                            <ont>{ont_id}</ont>
                                        </id>
                                    </object>
                                    <bin-type>1-day</bin-type>
                                    <start-bin>1</start-bin>
                                    <count>1</count>
                                </action-args>
                            </action>
                            </rpc>
                            </soapenv:Body>
                            </soapenv:Envelope>"""

        resp = self.__post(payload)
        if resp is None:
            self.logger.error(f"Failed to pull errors for {ont_id} on {node_id}")
            return {}

        error_types = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.types")
        error_values = get(resp, "soapenv:Envelope.soapenv:Body.rpc-reply.action-reply.bin.val")
        if isinstance(error_types, str) and isinstance(error_values, str):
            error_types = error_types.split(" ")
            error_values = error_values.split(" ")
            for i in range(len(error_types)):
                info[error_types[i]] = error_values[i]

        return info

    @property
    def message_id(self):
        """
        Randomly generated number used as a unique identifier for requests
        :return:
        """
        return str(random.getrandbits(random.randint(2, 31)))

    @property
    def headers(self):
        """
        Headers used for every request
        :return:
        """
        return {"Content-Type": "text/xml;charset=ISO8859-1", "User-Agent": f"CMS_NBI_CONNECT-{self.username}"}

    def __post(self, payload, timeout=5):
        """
        Wrapper for requests.post adding error checking and xml parsing
        :param payload:
        :param timeout:
        :return:
        """
        self.logger.debug(f"POST {self.netconf_url}\n{payload}")

        try:
            resp = requests.post(url=self.netconf_url, headers=self.headers, data=payload, timeout=timeout)

        except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError) as e:
            self.logger.error(e)
            return None

        if resp.status_code != 200:
            self.logger.warning(f"status_code={resp.status_code}")

        try:
            data = xmltodict.parse(resp.content)
            self.logger.debug(json.dumps(data, indent=2))
            return data

        except xmltodict.ParsingInterrupted:
            self.logger.error(f"Parsing failed\n{resp.content}")
            return None

    def test(self):
        valid_ont_info = self.get_fiber_info("rsvt-pon-1", "18330")
        invalid_ont_info = self.get_fiber_info("rsvt-pon-1", "18333")
        self.logger.info(f"valid_ont: {json.dumps(valid_ont_info, indent=2)}")
        self.logger.info(f"invalid_ont: {json.dumps(invalid_ont_info, indent=2)}")
