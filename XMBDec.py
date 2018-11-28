import sys
import struct
import xml.etree.cElementTree as CET
from xml.dom import minidom
from xml.etree import ElementTree


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")
    
def readStringNT(f):
    chars = []
    while True:
        c = struct.unpack('c', f.read(1))[0]
        if c == b'\x00':
            return "".join(chars)
        chars.append(c)

class XMB:
    class XMBHeader:
        def __init__(self, file):
            self.read(file)
        
        def read(self, f):
            f.seek(0)
            self.magic = f.read(4).decode('ascii')
            self.numEntries = struct.unpack('<I', f.read(4))[0]
            self.numValues = struct.unpack('<I', f.read(4))[0]
            self.numProperties = struct.unpack('<I', f.read(4))[0]
            self.count4 = struct.unpack('<I', f.read(4))[0]
            
            self.pStrOffsets = struct.unpack('<I', f.read(4))[0]
            self.pEntriesTable = struct.unpack('<I', f.read(4))[0]
            self.pPropertiesTable = struct.unpack('<I', f.read(4))[0]
            self.extraEntry = struct.unpack('<I', f.read(4))[0]
            self.pStrTable1 = struct.unpack('<I', f.read(4))[0]
            self.pStrTable2 = struct.unpack('<I', f.read(4))[0]
            
    class XMBEntry:
        def __init__(self, file):
            self.properties = {}
            self.children = []
            self.parent = None
            self.name = ''
            self.read(file)
            
        def read(self, f):
            self.nameOffset = struct.unpack('<I', f.read(4))[0]
            self.numExpressions = struct.unpack('<h', f.read(2))[0]
            self.numChildren = struct.unpack('<h', f.read(2))[0]
            self.firstProp = struct.unpack('<h', f.read(2))[0]
            self.unk1 = struct.unpack('<h', f.read(2))[0]
            self.parentIndex = struct.unpack('<h', f.read(2))[0]
            self.unk2 = struct.unpack('<h', f.read(2))[0]

        def buildXML(self, parent):
            element = CET.SubElement(parent, self.name)
            for prop, val in self.properties.items():
                CET.SubElement(element, prop).text = val
            
    def __init__(self, file):
        self.header = None
        self.entries = []
        self.roots = []
        self.read(file)
        
    def read(self, f):
        self.header = XMB.XMBHeader(f)
        
        # read nodes #
        for x in range(0, self.header.numEntries):
            f.seek(self.header.pEntriesTable + x * 0x10)
            entry = XMB.XMBEntry(f)
            f.seek(self.header.pStrTable1 + entry.nameOffset)         
            entry.name = readStringNT(f)
                      
            # setup node properties #
            for x in range(0, entry.numExpressions):
                f.seek(self.header.pPropertiesTable + (entry.firstProp + x) * 8)
                strOff1 = struct.unpack('<I', f.read(4))[0]
                strOff2 = struct.unpack('<I', f.read(4))[0]
                f.seek(self.header.pStrTable1 + strOff1)
                prop = readStringNT(f)
                f.seek(self.header.pStrTable2 + strOff2)
                entry.properties[prop] = readStringNT(f)
            self.entries.append(entry)
            
        # order nodes in a tree #
        for x in range(0, len(self.entries)):
            entry = self.entries[x]
            if entry.parentIndex != -1:
                entry.parent = self.entries[entry.parentIndex]

                y = 0
                while y < self.entries[entry.parentIndex + y].numChildren:
                    self.entries[entry.parentIndex + y].children.append(entry)
                    y += 1
            else:
                self.roots.append(entry)
        
    def print_info(self):
        print('Values:   {}'.format(hex(self.header.numValues)))
        print('Props:    {}'.format(hex(self.header.numProperties)))
        print('Entries:  {}'.format(hex(self.header.numEntries)))
        print('UnkCount: {}'.format(hex(self.header.count4)))
        print('')
        print('Roots:')
        for x in self.roots:
            print('    ' + x.name)
    
    def toXML(self):
        for x in self.roots:
            root = CET.Element(x.name)
            for child in x.children:
                child.buildXML(root)    
            print(prettify(root))
            
with open(sys.argv[1], 'rb') as f:
    xmb = XMB(f)
    xmb.toXML()