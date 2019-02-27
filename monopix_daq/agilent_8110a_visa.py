import visa
import string

class agilent_8110a_visa (object):
    def __init__(self, gpib):
        rm = visa.ResourceManager('C:\\Windows\\system32\\visa32.dll')
        resource = 'GPIB0::' + str(gpib) + '::INSTR'
        self._intf = rm.open_resource(resource)
        print 'Found', (self._intf.query("*IDN?"))
        
        self._scpi_commands = {'set_burst' : 'BURST:STAT',
        'get_burst' : 'BURST:STAT?',
        'set_n_bursts' : 'BURS:NCYC',
        'set_pulse_period' : 'PULS:PER',
        'set_pulse_width' : 'PULS:WIDT',
        'set_trigger_delay' : 'TRIG:DELAY',
        'get_voltage_high' : 'VOLT:HIGH?',
        'get_voltage_low' : 'VOLT:LOW?',
        'set_voltage_high' : 'VOLT:HIGH',
        'set_voltage_low' : 'VOLT:LOW'}

    def __getattr__(self, name):
        '''called only on last resort if there are no attributes in the instance that match the name
        '''
        def method(*args, **kwargs):
            channel = kwargs.pop('channel', None)
            try:
                command = self._scpi_commands['channel %s' % channel][name] if channel is not None else self._scpi_commands[name]
            except:
                raise ValueError('SCPI command %s is not defined for %s' % (name, self.__class__))
            name_split = name.split('_', 1)
            if len(name_split) == 1:
                self._intf.write(command)
            elif len(name_split) == 2 and name_split[0] == 'set' and len(args) == 1 and not kwargs:
                self._intf.write(command + ' ' + str(args[0]))
            elif len(name_split) == 2 and name_split[0] == 'get' and not args and not kwargs:
                return self._intf.query(command)

        return method
    
    def set_voltage(self, low, high=0.75, unit='mV'):
        if unit == 'raw':
            raw_low, raw_high = low, high
        elif unit == 'V':
            raw_low, raw_high = low, high
        elif unit == 'mV':
            raw_low, raw_high = low * 0.001, high * 0.001
        else:
            raise TypeError("Invalid unit type.")
        self.set_voltage_high(raw_high)
        self.set_voltage_low(raw_low)

    def get_voltage(self, channel, unit='mV'):
        raw_low, raw_high = string.atof(self.get_voltage_low()), string.atof(self.get_voltage_high())
        if unit == 'raw':
            return raw_low, raw_high
        elif unit == 'V':
            return raw_low, raw_high
        elif unit == 'mV':
            return raw_low * 1000, raw_high * 1000
        else:
            raise TypeError("Invalid unit type.")

