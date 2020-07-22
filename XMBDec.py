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

def writeStringNT(f,string):
    for c in string:
        f.write(c.encode('ASCII'))
    f.write(struct.pack('b',0))
    return f.tell()

def alignFile(f, alignment):
    while f.tell() % alignment:
        f.write(struct.pack('b',0))
    return f.tell()

class XMB:
    class XMBHeader:
        def __init__(self):
            self.magic = "XMB "
            self.numNodes = 0
            self.numValues = 0
            self.numProperties = 0

            self.numMappedNodes = 0
            self.pStrOffsets = -1
            self.pNodesTable = -1
            self.pPropertiesTable = -1
            
            self.pNodeMap = -1
            self.pStrNames = -1
            self.pStrValues = -1
            self.padding = 0
            
    class XMBEntry:
        def __init__(self):
            self.properties = {}
            self.children = []
            self.parent = None
            self.name = ''
            self.index = 0

            self.nameOffset = -1
            self.numProps = 0
            self.numChildren = 0
            self.firstProp = -1
            self.unk1 = -1
            self.parentIndex = -1
            self.unk2 = -1

        def toXml(self, parent):
            if self.parentIndex == -1 or parent == None:
                element = CET.Element(self.name)
            else:
                element = CET.SubElement(parent, self.name)
                
            for prop, val in self.properties.items():
                element.set(prop, val)               
            for child in self.children:
                child.toXml(element)              
            return element
            
        def print_info(self):
            print('{}: {}({}, {}, {}, {}, {}, {})'.format(self.index, self.name, 
                                                          self.numProps, self.numChildren, self.firstProp, self.unk1, self.parentIndex, self.unk2))
            
    def __init__(self, bigendian=False):
        if bigendian:
            self.endian = '>'
        else:
            self.endian = '<'
        self.header = None
        self.root = None
        self.nodes = []
        self.nodeDict = {}

    @classmethod
    def fromXmb(cls, path, bigendian=False):
        f = open(path,'rb')
        xmb = cls(bigendian)
        xmb.header = XMB.XMBHeader()

        # read header
        xmb.header.magic = f.read(4).decode('ascii')
        assert xmb.header.magic == "XMB ", "Invalid XMBHeader!"
        xmb.header.numNodes = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.numValues = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.numProperties = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.numMappedNodes = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pStrOffsets = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pNodesTable = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pPropertiesTable = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pNodeMap = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pStrNames = struct.unpack(xmb.endian+'I', f.read(4))[0]
        xmb.header.pStrValues = struct.unpack(xmb.endian+'I', f.read(4))[0]
        
        # nodes #
        for x in range(0, xmb.header.numNodes):
            f.seek(xmb.header.pNodesTable + x * 0x10)
            entry = XMB.XMBEntry()
            
            # read nodes from table
            entry.nameOffset = struct.unpack(xmb.endian+'I', f.read(4))[0]
            entry.numProps = struct.unpack(xmb.endian+'h', f.read(2))[0]
            entry.numChildren = struct.unpack(xmb.endian+'h', f.read(2))[0]
            entry.firstProp = struct.unpack(xmb.endian+'h', f.read(2))[0]
            entry.unk1 = struct.unpack(xmb.endian+'h', f.read(2))[0]
            entry.parentIndex = struct.unpack(xmb.endian+'h', f.read(2))[0]
            entry.unk2 = struct.unpack(xmb.endian+'h', f.read(2))[0]
            f.seek(xmb.header.pStrNames + entry.nameOffset)         
            entry.name = readStringNT(f)
            entry.index = x
            
            # setup node properties #
            for y in range(0, entry.numProps):
                f.seek(xmb.header.pPropertiesTable + (entry.firstProp + y) * 8)
                strOff1 = struct.unpack(xmb.endian+'I', f.read(4))[0]
                strOff2 = struct.unpack(xmb.endian+'I', f.read(4))[0]
                f.seek(xmb.header.pStrNames + strOff1)
                prop = readStringNT(f)
                f.seek(xmb.header.pStrValues + strOff2)
                entry.properties[prop] = readStringNT(f)
            xmb.nodes.append(entry)
            
        for x in range(0, xmb.header.numMappedNodes):
            f.seek(xmb.header.pNodeMap + x * 8)
            strOff1 = struct.unpack(xmb.endian+'I', f.read(4))[0]
            nodeIndex = struct.unpack(xmb.endian+'I', f.read(4))[0]
            f.seek(xmb.header.pStrValues + strOff1)
            nodeID = readStringNT(f)
            xmb.nodeDict[nodeID] = nodeIndex
            
        # order nodes in a tree #
        for x in range(0, len(xmb.nodes)):
            entry = xmb.nodes[x]
            if entry.parentIndex != -1:
                entry.parent = xmb.nodes[entry.parentIndex]
                xmb.nodes[entry.parentIndex].children.append(entry)
            else:
                xmb.root = entry
        f.close()
        return xmb
        
    # TODO clean this up. it's confusing and hacky
    @classmethod
    def fromXml(cls, path):
        xmb = XMB()
        tree = CET.parse(path)
        nodes = {}
        index = 0
        parent_map = dict((c, p) for p in tree.getiterator() for c in p)
        for e in tree.iter():
            entry = XMB.XMBEntry()
            entry.name = e.tag
            for prop,val in e.items():
                entry.properties[prop] = val
            entry.index = index
            entry.numProps = len(e.items())
            # can't get root's parent
            if index == 0:
                xmb.root = entry
            else:
                el = parent_map[e]
                entry.parent = nodes[el.tag]
                entry.parentIndex = entry.parent.index
                entry.parent.children.append(entry)
                entry.parent.numChildren = len(el)
            nodes[entry.name] = entry
            index += 1
        xmb.nodes = list(nodes.values())
        return xmb
        # print(xmb.toXML())

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
        xml = self.root.toXml(None) 
        return prettify(xml)

    def toXmb(self, path):
        f = open(path,'wb')
        names = []
        props = []
        values = []
        nameOffsets = {}
        valOffsets = {}
        for n in self.nodes:
            if n.name not in names:
                names.append(n.name)
            for prop,val in n.properties.items():
                props.append((prop,val))
                if prop not in names:
                    names.append(prop)
                if val not in values:
                    values.append(val)

        pStrOffsets = 0x40
        pNodeTable = pStrOffsets + 0x04 * len(names)
        pPropTable = pNodeTable + 0x10 * len(self.nodes)
        pNameStrs = pPropTable + len(props) * 0x8
        # write name strings
        f.seek(pNameStrs)
        for string in names:
            nameOffsets[string] = f.tell() - pNameStrs
            writeStringNT(f,string)
        # write value strings
        pValueStrs = alignFile(f, 0x04)
        for val in values:
            valOffsets[val] = f.tell() - pValueStrs
            writeStringNT(f,val)
        alignFile(f, 0x04)
        # write str offsets
        f.seek(pStrOffsets)
        for string in sorted(nameOffsets.keys()):
            f.write(struct.pack(self.endian+'I',nameOffsets[string]))
        # write node table
        f.seek(pNodeTable)
        propIdx = 0
        for nodeIdx, n in enumerate(self.nodes):
            f.seek(pNodeTable + (0x10 * nodeIdx))
            f.write(struct.pack(self.endian+'I',nameOffsets[n.name]))
            f.write(struct.pack(self.endian+'h',n.numProps))
            f.write(struct.pack(self.endian+'h',n.numChildren))
            f.write(struct.pack(self.endian+'h',propIdx))
            if len(n.children) > 0:
                n.unk1 = self.nodes.index(n.children[0])
            f.write(struct.pack(self.endian+'h',n.unk1))
            f.write(struct.pack(self.endian+'h',n.parentIndex))
            f.write(struct.pack(self.endian+'h',-1)) # not used / padding
            # write node's props
            f.seek(pPropTable + (0x8 * propIdx))
            for name,val in n.properties.items():
                f.write(struct.pack(self.endian+'I',nameOffsets[name]))
                f.write(struct.pack(self.endian+'I',valOffsets[val]))
                propIdx += 1
        # write header
        f.seek(0)
        f.write("XMB ".encode('ascii'))
        f.write(struct.pack(self.endian+'I',len(self.nodes)))
        f.write(struct.pack(self.endian+'I',len(props)))
        f.write(struct.pack(self.endian+'I',len(names)))
        f.write(struct.pack(self.endian+'I',0)) # nodemap, unsupported. Yell at @SammiHusky on twitter
        f.write(struct.pack(self.endian+'I',pStrOffsets))
        f.write(struct.pack(self.endian+'I',pNodeTable))
        f.write(struct.pack(self.endian+'I',pPropTable))
        f.write(struct.pack(self.endian+'I',pNameStrs)) # nodemap, unsupported. Yell at @SammiHusky on twitter
        f.write(struct.pack(self.endian+'I',pNameStrs))
        f.write(struct.pack(self.endian+'I',pValueStrs))
        f.close()


class MyParser(argparse.ArgumentParser): 
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)
      
parser = MyParser(usage='%(prog)s [options] Input File')
parser.add_argument("file", help="Input file", metavar="Input File")
parser.add_argument("-i", "--showinfo", help="Prints information about the XMB File", action="store_true", default=False)
parser.add_argument("-be", "--bigendian", help="Sets the script to Big Endian mode", action="store_true", default=False)
parser.add_argument("-o", help="Sets output File", metavar="OUTPUT", nargs="?", dest="output", default=None)
args = parser.parse_args()


if args.file.endswith('.xmb'):
    xmbFile = XMB.fromXmb(args.file)
    if args.showinfo:
        xmbFile.print_info()
        exit()
    content = xmbFile.toXML()
    if args.output != None:
        with open(args.output,'w+') as ofile:
            ofile.write(content)
    else:
        print(content)
elif args.file.endswith('.xml'):
    xmb = XMB.fromXml(args.file)
    xmb.toXmb("test.xmb")
    print('built xmb')
else:
    print('invalid input file.')
    parser.print_help()