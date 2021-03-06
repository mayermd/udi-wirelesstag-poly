"""
This is a NodeServer for CAO Gadgets Wireless Sensor Tags for Polyglot v2 written in Python3
by JimBoCA jimboca3@gmail.com
"""
import polyinterface
import sys
import time
import re
from copy import deepcopy
from wt_funcs import id_to_address,myfloat

LOGGER = polyinterface.LOGGER
DLEV = 0

class wTag(polyinterface.Node):
    """
    This is the class that all the Nodes will be represented by. You will add this to
    Polyglot/ISY with the controller.addNode method.

    Class Variables:
    self.primary: String address of the Controller node.
    self.parent: Easy access to the Controller Class from the node itself.
    self.address: String address of this Node 14 character limit. (ISY limitation)
    self.added: Boolean Confirmed added to ISY

    Class Methods:
    start(): This method is called once polyglot confirms the node is added to ISY.
    setDriver('ST', 1, report = True, force = False):
        This sets the driver 'ST' to 1. If report is False we do not report it to
        Polyglot/ISY. If force is True, we send a report even if the value hasn't changed.
    reportDrivers(): Forces a full update of all drivers to Polyglot/ISY.
    query(): Called when ISY sends a query request to Polyglot for this specific node
    """

    def __init__(self, controller, primary, address=None, name=None,
                 tag_type=None, uom=None, tdata=None, node_data=None):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.

        :param controller: Reference to the Controller class
        :param primary: Controller address
        :param address: This nodes address
        :param name: This nodes name
        """
        LOGGER.debug('wTag:__init__: address={0} name={1} type={2} uom={3}'.format(address,name,tag_type,uom))
        tag_id = None
         # So logger calls won't crash
        self.address = address
        self.id = 'wTag' # Until we figure out the uom
        self.name = name
        if node_data is not None:
            # An existing node,
            self.is_new = False
            # We need to pull tag_type from GV1 for existing tags.
            self.tag_uom = -1 # Should never happen, just need for old data added before it existed.
            for driver in node_data['drivers']:
                if driver['driver'] == 'GV1':
                    tag_type = driver['value']
                elif driver['driver'] == 'GPV':
                    tag_id   = driver['value']
                elif driver['driver'] == 'UOM':
                    self.tag_uom  = driver['value']
            if tag_id is None:
                self.l_error('__init__','No tag_id (GPV) in node_data={0}'.format(node_data))
                return False
            if tag_type is None:
                self.l_error('__init__','No tag_type (GV1) in node_data={0}'.format(node_data))
                return False
        elif address is None or name is None or tag_type is None:
            # It's a new tag.
            self.address = address
            if tdata is None:
                self.l_error('__init__',"address ({0}), name ({1}), and type ({2}) must be specified when tdata is None".format(address,name,tag_type))
                return False
            if uom is None:
                self.l_error('__init__',"uom ({0}) must be specified for new tags.".format(uom))
            self.is_new   = True
            tag_type      = tdata['tagType']
            self.tag_uom  = uom
            tag_id        = tdata['slaveId']
            self.uuid     = tdata['uuid']
            address       = id_to_address(self.uuid)
            name          = tdata['name']
        tag_id = int(tag_id)
        tag_type = int(tag_type)
        self.name = name
        self.tdata = tdata
        self.tag_id = tag_id
        self.tag_type = tag_type
        self.primary_n = controller.nodes[primary]
        #
        # C or F?
        # Fix our temp_uom in drivers
        # This won't change an existing tag, only new ones.
        #
        # TODO:  test changing it by forcing update?
        temp_uom = 4 if self.tag_uom == 0 else 17
        dv = [
            {'driver': 'ST',      'value': 0, 'uom': 2},
             # tag_id
            {'driver': 'GPV',     'value': self.tag_id, 'uom': 56},
            # UOM 0=C 1=F
            {'driver': 'UOM',     'value': 0, 'uom': 56},
            # tag_type:
            {'driver': 'GV1',     'value': self.tag_type, 'uom': 56},
            # temp:   Curent temperature (17=F 4=C)
            {'driver': 'CLITEMP', 'value': 0, 'uom': temp_uom},
            # batp:   Battery percent (51=percent)
            {'driver': 'BATLVL',  'value': 0, 'uom': 51},
            # batv:   Battery Voltag 72=Volt
            {'driver': 'CV',      'value': 0, 'uom': 72},
            # lit:    Light
            {'driver': 'GV7',     'value': 0, 'uom': 25},
            # tempState:
            {'driver': 'GV9',     'value': 0, 'uom': 25},
            # time:
            {'driver': 'GV13',     'value': 0, 'uom': 25},
            # seconds since update
            {'driver': 'GV14',     'value': 0, 'uom': 25},
        ]

        if (tag_type == 12 or tag_type == 13 or tag_type == 21 or tag_type == 26
            or tag_type == 32 or tag_type == 52 or tag_type == 62 or
            tag_type == 72):
            # evst: Event State
            dv.append({'driver': 'ALARM',   'value': 0, 'uom': 25})
        if (tag_type == 26):
            # lux:    Lux (36=lux)
            dv.append({'driver': 'LUMIN',   'value': 0, 'uom': 36})
        if (tag_type == 13 or tag_type == 21 or tag_type == 26 or tag_type == 32
            or tag_type == 52 or tag_type == 62 or tag_type == 72):
            # hum:    Humidity (21 = absolute humidity)
            dv.append({'driver': 'CLIHUM',  'value': 0, 'uom': 22})
        if (tag_type == 12 or tag_type == 13 or tag_type == 21):
            # motion: Might use True, False, Open for door mode?
            dv.append({'driver': 'GV2',     'value': 0, 'uom': 25})
            # orien:  Orientation
            dv.append({'driver': 'GV3',     'value': 0, 'uom': 56})
            # xaxis:  X-Axis
            dv.append({'driver': 'GV4',     'value': 0, 'uom': 56})
            # yasis:  Y-Axis
            dv.append({'driver': 'GV5',     'value': 0, 'uom': 56})
            # zaxis:  Z-Axis
            dv.append({'driver': 'GV6',     'value': 0, 'uom': 56})
        if (tag_type == 12 or tag_type == 13 or tag_type == 21 or tag_type == 26
            or tag_type == 32 or tag_type == 52 or tag_type == 72):
            # oor:    OutOfRange
            dv.append({'driver': 'GV8',     'value': 0, 'uom':  2})
            # signaldBm:
            dv.append({'driver': 'CC',     'value': 0, 'uom':  56})
        if (tag_type == 13 or tag_type == 21 or tag_type == 26
            or tag_type == 32 or tag_type == 52 or tag_type == 62
            or tag_type == 72):
            # moisture(cap)State:
            dv.append({'driver': 'GV10',    'value': 0, 'uom': 25})
        if (tag_type == 26):
            # lightState:
            dv.append({'driver': 'GV11',    'value': 0, 'uom': 25})
        if (tag_type == 32):
            # TODO: Only 32 has water sensor?
            dv.append({'driver': 'GV12',  'value': 1, 'uom': 25})
        self.drivers = dv
        uomS = "C" if self.tag_uom == 0 else "F"
        self.id = 'wTag' + str(self.tag_type) + uomS
        self.address = address
        self.l_info('__init__','address={0} name={1} type={2} id={3} uom={4}'.format(address,name,self.tag_type,self.tag_id,self.tag_uom))
        super(wTag, self).__init__(controller, primary, address, name)

    def start(self):
        """
        Optional.
        This method is run once the Node is successfully added to the ISY
        and we get a return result from Polyglot. Only happens once.
        """
        # Always set driver from tag type
        self.set_tag_type(self.tag_type)
        self.set_tag_id(self.tag_id)
        self.set_tag_uom(self.tag_uom)
        if self.tdata is not None:
            self.set_from_tag_data(self.tdata)
        else:
            # These stay the same across reboots as the default.
            self.get_set_alive()
            self.get_set_temp()
            self.get_set_hum()
            self.get_set_lux()
            self.get_set_batp()
            self.get_set_batv()
            self.get_set_motion()
            self.get_set_orien()
            self.get_set_xaxis()
            self.get_set_yaxis()
            self.get_set_zaxis()
            self.get_set_lit()
            self.get_set_evst()
            self.get_set_oor()
            self.get_set_signaldbm()
            self.get_set_tmst()
            self.get_set_cpst()
            self.get_set_list()
            self.get_set_wtst()
            self.set_time_now()
        if self.controller.update_profile:
            # Drivers were updated, need to query
            self.query()
        else:
            # Otherwise just report previous values
            self.reportDrivers()

    def shortPoll(self):
        self.set_seconds()

    def query(self):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        # Polyglot bug?  We have to set every driver before calling reportDrivers?
        #self.set_tag_type(self.tag_type,True)
        #self.set_tag_id(self.tag_id,True)
        #self.set_tag_uom(self.tag_uom,True)
        # This askes for the sensor to report
        mgd = self.controller.wtServer.RequestImmediatePostback({'id':self.tag_id})
        if mgd['st']:
            self.set_from_tag_data(mgd['result'])
            self.reportDrivers()

    def l_info(self, name, string):
        LOGGER.info("%s:%s:%s:%s:%s: %s" %  (self.primary_n.name,self.name,self.address,self.id,name,string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s:%s:%s:%s: %s" % (self.primary_n.name,self.name,self.address,self.id,name,string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s:%s:%s:%s: %s" % (self.primary_n.name,self.name,self.address,self.id,name,string))

    def l_debug(self, name, string):
        LOGGER.debug("%s:%s:%s:%s:%s: %s" % (self.primary_n.name,self.name,self.address,self.id,name,string))

    def get_handler(self,command,params):
        """
        This is called by the controller get_handler after parsing the node_data
        """
        if command == '/update':
            #tagname=Garage Freezer&tagid=0&temp=-21.4213935329179&hum=0&lux=0&ts=2018-02-15T11:18:02+00:00 HTTP/1.1" 400 -
            pass
        elif command == '/motion_detected':
            self.set_motion(1)
        elif command == '/motion_timedout':
            self.set_motion(0)
        elif command == '/door_opened':
            self.set_motion(2)
        elif command == '/door_closed':
            self.set_motion(4)
        elif command == '/door_open_toolong':
            self.set_motion(2)
        elif command == '/oor':
            self.set_oor(1)
        elif command == '/back_in_range':
            self.set_oor(0)
        elif command == '/temp_normal':
            self.set_tmst(1)
        elif command == '/temp_toohigh':
            self.set_tmst(2)
        elif command == '/temp_toolow':
            self.set_tmst(3)
        elif command == '/too_humid':
            self.set_cpst(4)
        elif command == '/too_dry':
            self.set_cpst(3)
        elif command == '/cap_normal':
            self.set_cpst(2)
        elif command == '/water_detected':
            self.set_wtst(2)
        elif command == '/water_dried':
            self.set_wtst(1)
        elif command == '/low_battery':
            self.set_batl(1)
        elif command == '/too_bright':
            self.set_list(4)
        elif command == '/too_dark':
            self.set_list(3)
        elif command == '/light_normal':
            self.set_list(2)
        else:
            self.l_error('get_handler',"Unknown command '{0}'".format(command))
        if 'tempc' in params and self.tag_uom == 0:
            self.set_temp(params['tempc'],convert=False)
        if 'tempf' in params and self.tag_uom == 1:
            self.set_temp(params['tempf'],convert=False)
        if 'temp' in params:
            self.set_temp(params['temp'])
        if 'hum' in params:
            self.set_hum(params['hum'])
        if 'lux' in params:
            self.set_lux(params['lux'])
        if 'orien' in params:
            self.set_orien(params['orien'])
        if 'xaxis' in params:
            self.set_xaxis(params['xaxis'])
        if 'yaxis' in params:
            self.set_yaxis(params['yaxis'])
        if 'zaxis' in params:
            self.set_zaxis(params['zaxis'])
        self.set_time_now()
        return True

    """
    Set Functions
    """
    def set_from_tag_data(self,tdata):
        if 'alive' in tdata:
            self.set_alive(tdata['alive'])
        if 'temperature' in tdata:
            self.set_temp(tdata['temperature'])
        if 'batteryVolt' in tdata:
            self.set_batv(tdata['batteryVolt'])
        if 'batteryRemaining' in tdata:
            self.set_batp(float(tdata['batteryRemaining']) * 100)
        if 'lux' in tdata:
            self.set_lux(tdata['lux'])
        if 'cap' in tdata:
            self.set_hum(tdata['cap'])
        if 'lit' in tdata:
            self.set_lit(tdata['lit'])
        if 'eventState' in tdata:
            self.set_evst(tdata['eventState'])
        if 'oor' in tdata:
            self.set_oor(tdata['oor'])
        if 'signaldBm' in tdata:
            self.set_signaldbm(tdata['signaldBm'])
        if 'tempEventState' in tdata:
            self.set_tmst(tdata['tempEventState'])
        if 'capEventState' in tdata:
            self.set_cpst(tdata['capEventState'])
        if 'lightEventState' in tdata:
            self.set_list(tdata['lightEventState'])
        # This is the last time the tag manager has heard from the tag?
        if 'lastComm' in tdata:
            self.set_time(tdata['lastComm'],wincrap=True)
            self.set_seconds()

    # This is the tag_type number, we don't really need to show it, but
    # we need the info when recreating the tags from the config.
    def set_tag_type(self,value):
        self.l_debug('set_tag_type','GV1 to {0}'.format(value))
        self.tag_type = value
        self.setDriver('GV1', value)

    def set_tag_id(self,value):
        self.l_debug('set_tag_id','GPV to {0}'.format(value))
        self.tag_id = value
        self.setDriver('GPV', value)

    def set_tag_uom(self,value):
        self.l_debug('set_tag_uom','UOM to {0}'.format(value))
        self.tag_uom = value
        self.setDriver('UOM', value)

    def get_set_alive(self):
        self.set_alive(self.getDriver('ST'))

    def set_alive(self,value):
        self.l_debug('set_alive','{0}'.format(value))
        self.setDriver('ST', int(value))

    def get_set_temp(self):
        self.set_temp(self.getDriver('CLITEMP'),False)

    def set_temp(self,value,convert=True):
        self.l_debug('set_temp','{0},{1}'.format(value,convert))
        if convert and self.primary_n.degFC == 1:
            # Convert C to F
            value = float(value) * 1.8 + 32.0
        value = myfloat(value,1)
        self.setDriver('CLITEMP', value)

    def get_set_hum(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('CLIHUM')
        if value is None: return
        self.set_hum(value)

    def set_hum(self,value):
        self.l_debug('set_hum','{0}'.format(value))
        self.setDriver('CLIHUM', myfloat(value,1))

    def get_set_lit(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV7')
        if value is None: return
        self.set_lit(value)

    def set_lit(self,value):
        self.l_debug('set_lit','{0}'.format(value))
        self.setDriver('GV7', int(value))

    def get_set_lux(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('LUMIN')
        if value is None: return
        self.set_lux(value)

    def set_lux(self,value):
        self.l_debug('set_lux','{0}'.format(value))
        self.setDriver('LUMIN', myfloat(value,2))

    def get_set_batp(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('BATLVL')
        if value is None: return
        self.set_batp(value)

    def set_batp(self,value,force=False):
        self.l_debug('set_batp','{0}'.format(value))
        self.setDriver('BATLVL', myfloat(value,2))

    def get_set_batv(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('CV')
        if value is None: return
        self.set_batv(value)

    def set_batv(self,value):
        self.setDriver('CV', myfloat(value,3))

    def set_batl(self,value,force=False):
        # TODO: Implement battery low!
        return
        self.setDriver('CV', value)

    def get_set_motion(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV2')
        if value is None: return
        self.set_motion(value)

    def set_motion(self,value=None):
        self.l_debug('set_motion','{0}'.format(value))
        value = int(value)
        # Not all have motion, but that's ok, just sent it.
        self.setDriver('GV2', value)
        if value == 0: # False
            self.set_evst(1,andMotion=False) # Armed
        elif value == 1: # True
            self.set_evst(5,andMotion=False) # Detected Movement
        if value == 2: # Door Open
            self.set_evst(3,andMotion=False) # Opened
        elif value == 3: # Open too long
            self.set_evst(3,andMotion=False) # Opened
        elif value == 4: # Closed
            self.set_evst(4,andMotion=False) # Closed


    def get_set_orien(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV3')
        if value is None: return
        self.set_orien(value)

    def set_orien(self,value):
        self.l_debug('set_orien','{0}'.format(value))
        self.setDriver('GV3', myfloat(value,1))

    def get_set_xaxis(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV4')
        if value is None: return
        self.set_xaxis(value)

    def set_xaxis(self,value):
        self.l_debug('set_xaxis','{0}'.format(value))
        self.setDriver('GV4', int(value))

    def get_set_yaxis(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV5')
        if value is None: return
        self.set_yaxis(value)

    def set_yaxis(self,value):
        self.l_debug('set_yaxis','{0}'.format(value))
        self.setDriver('GV5', int(value))

    def get_set_zaxis(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV6')
        if value is None: return
        self.set_zaxis(value)

    def set_zaxis(self,value):
        self.l_debug('set_zaxis','{0}'.format(value))
        self.setDriver('GV6', int(value))

    def get_set_evst(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('ALARM')
        if value is None: return
        self.set_evst(value)

    def set_evst(self,value,andMotion=True):
        self.l_debug('set_evst','{0}'.format(value))
        self.setDriver('ALARM', int(value))
        # eventState 1=Armed, so no more motion
        if andMotion and int(value) == 1:
            self.set_motion(0)

    def get_set_oor(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV8')
        if value is None: return
        self.set_oor(value)

    def set_oor(self,value):
        self.l_debug('set_oor','{0}'.format(value))
        self.setDriver('GV8', int(value))

    def get_set_signaldbm(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('CC')
        if value is None: return
        self.set_signaldbm(value)

    def set_signaldbm(self,value):
        self.l_debug('set_signaldbm','{0}'.format(value))
        self.setDriver('CC', int(value))

    def get_set_tmst(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV9')
        if value is None: return
        self.set_tmst(value)

    def set_tmst(self,value):
        self.l_debug('set_tmst','{0}'.format(value))
        self.setDriver('GV9', int(value))

    def get_set_cpst(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV10')
        if value is None: return
        self.set_cpst(value)

    def set_cpst(self,value):
        self.l_debug('set_cpst','{0}'.format(value))
        self.setDriver('GV10', int(value))

    def get_set_list(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV11')
        if value is None: return
        self.set_list(value)

    def set_list(self,value):
        self.l_debug('set_list','{0}'.format(value))
        self.setDriver('GV11', int(value))

    def get_set_wtst(self):
        # Get current value, if None then we don't have this driver.
        value = self.getDriver('GV12')
        if value is None: return
        self.set_wtst(value)

    def set_wtst(self,value):
        self.l_debug('set_wtst','{0}'.format(value))
        # Force to 1, Dry state on initialization since polyglot ignores the init value
        value = int(value)
        if value == 0: value = 1
        self.setDriver('GV12', int(value))

    def set_time_now(self):
        self.set_time(int(time.time()))
        self.set_seconds()

    def set_time(self,value,wincrap=False):
        self.l_debug('set_time','{0},{1}'.format(value,wincrap))
        value = int(value)
        if wincrap:
            # Convert windows timestamp to unix :(
            # https://stackoverflow.com/questions/10411954/convert-windows-timestamp-to-date-using-php-on-a-linux-box
            value = int(value / 10000000 - 11644477200)
            self.l_debug('set_time','{0}'.format(value))
        self.time = value
        self.setDriver('GV13', self.time)

    def set_seconds(self,force=True):
        if not hasattr(self,"time"): return False
        time_now = int(time.time())
        if DLEV > 0: self.l_debug('set_seconds','time_now    {}'.format(time_now))
        if DLEV > 0: self.l_debug('set_seconds','last_time - {}'.format(self.time))
        if self.time == 0:
            value = -1
        else:
            value = time_now - self.time
        if DLEV > 0:
            self.l_debug('set_seconds','          = {}'.format(value))
        else:
            self.l_debug('set_seconds','{}'.format(value))
        self.setDriver('GV14', value)

    """
    """

    def cmd_set_light(self,command):
        value = int(command.get("value"))
        # Save current value, and change it.
        slit = self.lit
        self.set_lit(value)
        if value == 0:
            ret = self.controller.wtServer.LightOff(self.primary_n.mac,self.tag_id)
        elif value == 1:
            ret = self.controller.wtServer.LightOn(self.primary_n.mac,self.tag_id,False)
        elif value == 2:
            ret = self.controller.wtServer.LightOn(self.primary_n.mac,self.tag_id,True)
        if ret['st']:
            self.set_from_tag_data(ret['result'])
        else:
            # Command failed, restore status
            self.set_lit(slit)

    commands = {
        'QUERY': query,
        'SET_LIGHT': cmd_set_light,
    }
