import sys
import struct
import argparse
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
        c = struct.unpack('b', f.read(1))[0]
        if c == 0x00:
            return "".join(chars)
        chars.append(chr(c))

class XMB:
    class XMBHeader:
        def __init__(self, file, bigendian=False):
            self.endian = '<'
            if bigendian:
                self.endian = '>'
            self.read(file, bigendian)
        
        def read(self, f, bigendian=False):
            f.seek(0)
            self.magic = f.read(4).decode('ascii')
            self.numNodes = struct.unpack(self.endian+'I', f.read(4))[0]
            self.numValues = struct.unpack(self.endian+'I', f.read(4))[0]
            self.numProperties = struct.unpack(self.endian+'I', f.read(4))[0]
            self.numMappedNodes = struct.unpack(self.endian+'I', f.read(4))[0]
            
            self.pStrOffsets = struct.unpack(self.endian+'I', f.read(4))[0]
            self.pNodesTable = struct.unpack(self.endian+'I', f.read(4))[0]
            self.pPropertiesTable = struct.unpack(self.endian+'I', f.read(4))[0]
            self.pNodeMap = struct.unpack(self.endian+'I', f.read(4))[0]
            self.pStrNames = struct.unpack(self.endian+'I', f.read(4))[0]
            self.pStrValues = struct.unpack(self.endian+'I', f.read(4))[0]
            
    class XMBEntry:
        def __init__(self, file, bigendian=False):
            self.endian = '<'
            if bigendian:
                self.endian = '>'
            self.properties = {}
            self.children = []
            self.parent = None
            self.name = ''
            self.index = 0
            self.read(file, bigendian)
            
        def read(self, f, bigendian=False):
            self.nameOffset = struct.unpack(self.endian+'I', f.read(4))[0]
            self.numProps = struct.unpack(self.endian+'h', f.read(2))[0]
            self.numChildren = struct.unpack(self.endian+'h', f.read(2))[0]
            self.firstProp = struct.unpack(self.endian+'h', f.read(2))[0]
            self.unk1 = struct.unpack(self.endian+'h', f.read(2))[0]
            self.parentIndex = struct.unpack(self.endian+'h', f.read(2))[0]
            self.unk2 = struct.unpack(self.endian+'h', f.read(2))[0]

        def buildXML(self, parent):
            if self.parentIndex == -1 or parent == None:
                element = CET.Element(self.name)
            else:
                element = CET.SubElement(parent, self.name)
                
            for prop, val in self.properties.items():
                element.set(prop, val)               
            for child in self.children:
                child.buildXML(element)              
            return element
            
        def print_info(self):
            print('{}: {}({}, {}, {}, {}, {}, {})'.format(self.index, self.name, 
                                                          self.numProps, self.numChildren, self.firstProp, self.unk1, self.parentIndex, self.unk2))
            
    def __init__(self, file, bigendian=False):
        self.endian = '<'
        if bigendian:
            self.endian = '>'
        self.header = None
        self.nodes = []
        self.roots = []
        self.nodeDict = {}
        self.read(file, bigendian)
        
    def read(self, f, bigendian=False):
        self.header = XMB.XMBHeader(f, bigendian)
        
        # read nodes #
        for x in range(0, self.header.numNodes):
            f.seek(self.header.pNodesTable + x * 0x10)
            entry = XMB.XMBEntry(f, bigendian)
            f.seek(self.header.pStrNames + entry.nameOffset)         
            entry.name = readStringNT(f)
            entry.index = x
            
            # setup node properties #
            for y in range(0, entry.numProps):
                f.seek(self.header.pPropertiesTable + (entry.firstProp + y) * 8)
                strOff1 = struct.unpack(self.endian+'I', f.read(4))[0]
                strOff2 = struct.unpack(self.endian+'I', f.read(4))[0]
                f.seek(self.header.pStrNames + strOff1)
                prop = readStringNT(f)
                f.seek(self.header.pStrValues + strOff2)
                entry.properties[prop] = readStringNT(f)
            self.nodes.append(entry)
            
        for x in range(0, self.header.numMappedNodes):
            f.seek(self.header.pNodeMap + x * 8)
            strOff1 = struct.unpack(self.endian+'I', f.read(4))[0]
            nodeIndex = struct.unpack(self.endian+'I', f.read(4))[0]
            f.seek(self.header.pStrValues + strOff1)
            nodeID = readStringNT(f)
            self.nodeDict[nodeID] = nodeIndex
            
        # order nodes in a tree #
        for x in range(0, len(self.nodes)):
            entry = self.nodes[x]
            if entry.parentIndex != -1:
                entry.parent = self.nodes[entry.parentIndex]
                self.nodes[entry.parentIndex].children.append(entry)
                
            else:
                self.roots.append(entry)
        
    def print_info(self):
        print('Values:       {}'.format(hex(self.header.numValues)))
        print('Props:        {}'.format(hex(self.header.numProperties)))
        print('nodes:        {}'.format(hex(self.header.numNodes)))
        print('Mapped Nodes: {}'.format(hex(self.header.numMappedNodes)))
        print('Node Map:     {}'.format(hex(self.header.pNodeMap)))
        print('PropTable:    {}'.format(hex(self.header.pStrNames)))
        print('ValTable:     {}'.format(hex(self.header.pStrValues)))
        print('')
        for x in self.nodes:
            x.print_info()
    
    def toXML(self):
        for x in self.roots:
            root = x.buildXML(None) 
        return prettify(root)
        
class MyParser(argparse.ArgumentParser): 
   def error(self, message):
      sys.stderr.write('error: %s\n' % message)
      self.print_help()
      sys.exit(2)
      
parser = MyParser(usage='%(prog)s [options] XMB File')
parser.add_argument("file", help="XMB File to decompile", metavar="XMB File")
parser.add_argument("-i", "--showinfo", help="Prints information about the XMB File", action="store_true", default=False)
parser.add_argument("-be", "--bigendian", help="Sets the script to Big Endian mode", action="store_true", default=False)
parser.add_argument("-o", help="Sets output File", metavar="OUTPUT", nargs="?", dest="output", default=None)

args = parser.parse_args()

with open(args.file, 'rb') as f:
    xmb = XMB(f, args.bigendian)
    if args.showinfo:
        xmb.print_info()
    else: 
        content = xmb.toXML()
        if args.output != None:
            with open(args.output,'w+') as ofile:
                ofile.write(content)
        else:
            print(content)