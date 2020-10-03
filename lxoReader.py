#!/usr/bin/python

# MIT License

# Copyright (c) 2020 Bernd Moeller

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import struct
import pprint
import argparse

try:
    from termcolor import colored
except ModuleNotFoundError:
    def colored(out, color):
        return out

global DEBUG
DEBUG = False

# The following website was used to get nearly all information
# about the LXO file format:
# https://modosdk.foundry.com/wiki/File_Formats

sENCODINGS = ['System Default', 'ANSI', 'UTF-8', 'Shift-JIS (Japanese)',
              'EUC-JP (Japanese)', 'EUC-KR (Korea KS C 5601)',
              'GB2312 (Simplified Chinese)', 'BIG5 (Traditional Chinese)']


class LXOLayer(object):
    def __init__(self, parent, name, subdLevel, psubLevel, id):
        self.__parent = parent
        self.name = name
        self.isSubD = False
        self.subdLevel = subdLevel
        self.psubLevel = psubLevel
        self.vertCount = 0
        self.polyCount = 0
        self.vmaps = None
        self.referenceID = id
        self.points = []
        self.polygons = []
        self.ptags = {}
        self.materials = {}
        self.uvMaps = {}
        self.uvMapsDisco = {}

    @property
    def parent(self):
        return self.__parent

    def generateMaterials(self):
        if 'MATR' not in self.ptags:
            return
        for data in self.ptags['MATR']:
            polyIndex, tagIndex = data
            materialName = self.parent.tagnames[tagIndex]
            if materialName not in self.materials:
                self.materials[materialName] = []
            self.materials[materialName].append(polyIndex)


class ActionLayer(object):
    def __init__(self, name, type, index):
        self.name = name
        self.type = type
        self.index = index
        self.__items = []

    def addItem(self, id):
        item = ActionLayerItem(id)
        self.__items.append(item)
        return item

    def itemIter(self):
        for item in self.__items:
            yield (item.id, item.CHAN, item.stringChannels)


class ActionLayerItem(object):
    def __init__(self, id):
        self.id = id
        self.CHAN = []
        self.GRAD = []
        self.stringChannels = []


class LXOItem(object):
    def __init__(self, name, id, typename):
        self.id = id
        self.name = name
        self.vname = None
        self.typename = typename
        self.channel = {}
        self.GRAD = []
        # self.stringChannels = []
        self.CHNL = []
        self.CHNV = {}
        self.itemTags = []
        self.packages = []
        self.UCHN = []
        self.CHNC = []
        self.CLNK = []
        self.graphLinks = {}
        self.LAYR = None


class LXOFile(object):
    def __init__(self):
        self.version = None
        self.appversion = None
        self.encoding = None
        self.size = 0
        self.type = None
        self.description = None
        self.__items = []
        self.__layers = []
        self.__actionLayers = []
        self.channelNames = None
        self.data = []
        self.tagnames = None
        self.IASS = dict()

    def addLayer(self, name, subdLevel, psubLevel, id):
        layer = LXOLayer(self, name, subdLevel, psubLevel, id)
        self.__layers.append(layer)
        return layer

    def addActionLayer(self, name, type, index):
        actionLayer = ActionLayer(name, type, index)
        self.__actionLayers.append(actionLayer)
        return actionLayer

    def addItem(self, name, id, typename):
        item = LXOItem(name, id, typename)
        self.__items.append(item)
        return item

    @property
    def items(self):
        for item in self.__items:
            yield item

    @property
    def layers(self):
        for layer in self.__layers:
            yield layer

    @property
    def actionLayers(self):
        for layer in self.__actionLayers:
            yield layer

    def pprint(self):
        for key, val in list(vars(self).items()):
            if key == 'channelNames' or key.startswith('_LXOFile_'):
                continue
            print(key, val)

        print('Layers: name polyCount')
        for layer in self.__layers:
            print(layer.name, layer.polyCount)

        print('action layers')
        for actl in self.__actionLayers:
            print(actl.name)
            for it in actl.itemIter():
                pprint.pprint(it)

        for item in self.__items:
            print(item.name, item.vname, item.typename)
            for ch, value in item.channel.items():
                print(" ", ch, value)
            for ch in item.GRAD:
                print(" ", ch)
            # for ch in item.stringChannels:
            #     print(" ", ch)
            for ch in item.CHNL:
                print(" ", ch)
            for ch, val in item.CHNV.items():
                print(" ", ch, val)
            for ch in item.itemTags:
                print(" ", ch)
            for ch, val in item.graphLinks.items():
                print(" ", ch, val)


class LXOReader(object):
    def __init__(self):
        self.file = None
        self.modSize = 0
        self.tagsToRead = set()

    def readID4(self):
        # 4-byte identifier encapsulated in a long.
        # This is usually a string of ASCII values, which can be generated with
        # some bit-shifting and bitwise or'ing like so:
        # ('T' << 24 | 'E' << 16 | 'S' << 8 | 'T').
        self.modSize -= 4
        val = struct.unpack(">1l", self.file.read(4))[0]
        return (chr(val >> 24) + chr(val >> 16 & 255) +
                chr(val >> 8 & 255) + chr(val & 255))

    def readU1(self):
        self.modSize -= 1
        return struct.unpack(">1B", self.file.read(1))[0]

    def readU14(self):
        self.modSize -= 4
        return [struct.unpack(">1B", self.file.read(1))[0] for v in range(4)]

    def readU1s(self):
        size = self.modSize
        self.modSize = 0
        return struct.unpack(">%ss" % size, self.file.read(size))[0]

    def readU2(self):
        # unsigned short
        self.modSize -= 2
        return struct.unpack(">1H", self.file.read(2))[0]

    def readU4(self):
        # unsigned long
        self.modSize -= 4
        return struct.unpack(">1L", self.file.read(4))[0]

    def readVX(self):
        # U2 if smaller than 0xFF00 otherwise U4
        val = self.file.read(2)
        out = struct.unpack(">1H", val)[0]
        if out < int('FF00', 16):
            self.modSize -= 2
            return out
        else:
            val += self.file.read(2)
            val = '\x00' + val[1:]  # discard first byte, feels hacky...
            self.modSize -= 4
            return struct.unpack(">1L", val)[0]

    def readI2(self):
        self.modSize -= 2
        return struct.unpack(">1h", self.file.read(2))[0]

    def readI4(self):
        self.modSize -= 4
        return struct.unpack(">1l", self.file.read(4))[0]

    def readF4(self):
        self.modSize -= 4
        return struct.unpack(">1f", self.file.read(4))[0]

    def readS0(self):
        # NULL-terminated ASCII string. The string is padded to an even number
        # of bytes with a NULL where necessary.
        s0 = b''
        while True:
            s0 += struct.unpack(">1s", self.file.read(1))[0]
            self.modSize -= 1
            if len(s0) % 2 == 0 and s0.endswith(b'\0'):
                s0 = s0.rstrip(b'\0')
                return s0.decode("utf-8", "ignore")

    def readInt(self):
        self.modSize -= 4
        return struct.unpack(">1i", self.file.read(4))[0]

    def readFloat(self):
        self.modSize -= 4
        return struct.unpack(">1f", self.file.read(4))[0]

    def readVEC12(self):
        vec = [self.readF4() for x in range(3)]
        return vec

    def readblob(self, size=None):
        if size is None:
            raise Exception('need blob size')
        self.modSize -= size
        cc = b''
        for c in range(size):
            cc += struct.unpack(">1c", self.file.read(1))[0]
        return cc

    def readValue(self, datatype):
        datatype = int(datatype) & ~0x20  # 33, 34, 35 exist as well...
        if datatype == 1 or datatype == 17:  # integer
            value = self.readInt()
        elif datatype == 2 or datatype == 18:  # float
            value = self.readFloat()
        # String representing an integer text hint.
        elif datatype == 3 or datatype == 19:
            value = self.readS0()
        else:
            raise Exception("unknown datatype")
            # blobsize = subchunkSize - (subsizeSnap - self.modSize)
            # value = self.readblob(blobsize)
        return value

    def readFromFile(self, filepath):
        if not filepath or not os.path.isfile(filepath):
            raise Exception('not a file')
        fileSize = os.stat(filepath).st_size
        if DEBUG:
            print(fileSize)
        lxoFile = LXOFile()
        with open(filepath, 'rb') as srcfile:
            self.file = srcfile
            # read main FORM chunkID and size
            form = struct.unpack(">4s", self.file.read(4))[0]
            size = struct.unpack(">1L", self.file.read(4))[0]
            self.modSize = size
            sceneType = self.readID4()
            # throw an error if it's not FORM
            if form != b'FORM':
                raise Exception('not a valid file')

            lxoFile.size = size
            lxoFile.type = sceneType

            self.__readChunks(lxoFile)
            self.file = None
        return lxoFile

    def __readChunks(self, lxoFile):
        # read all other chunks
        currentLayer = None
        while self.modSize > 0:
            chunkID = self.readID4()
            chunkSize = self.readU4()
            sizeSnap = self.modSize

            # only read the tags specified
            if self.tagsToRead and chunkID not in self.tagsToRead:
                self.modSize -= chunkSize
                self.file.seek(chunkSize, 1)
                continue

            if DEBUG:
                print(colored(chunkID, 'green'), end=" ")

            if chunkID == 'DESC':
                presetType = self.readS0()
                presetDescription = self.readS0()
                if DEBUG:
                    print(presetType, presetDescription)
            elif chunkID == 'VRSN':
                major = self.readU4()
                minor = self.readU4()
                app = self.readS0()
                lxoFile.version = major
                lxoFile.appversion = app
                if DEBUG:
                    print(major, minor, app)
            elif chunkID == 'APPV':
                major = self.readU4()
                minor = self.readU4()
                unknown = self.readU4()
                build = self.readU4()
                level = self.readS0()
                if DEBUG:
                    print(major, minor, unknown, build, level)
            elif chunkID == 'ENCO':
                encoding = self.readU4()
                lxoFile.encoding = encoding
                if DEBUG:
                    print(sENCODINGS[encoding])
            elif chunkID == 'TAGS':
                tags = []
                while (sizeSnap - self.modSize) < chunkSize:
                    tags.append(self.readS0())
                lxoFile.tagnames = tags
                if DEBUG:
                    print(tags)
            elif chunkID == 'CHNM':
                count = self.readU4()
                names = []
                for i in range(count):
                    names.append(self.readS0())
                lxoFile.channelNames = names
                if DEBUG:
                    print(names)
            elif chunkID == 'LAYR':
                indexLegacy = self.readU2()
                flags = self.readU2()
                rotPivot = self.readVEC12()
                name = self.readS0()
                parentLegacy = self.readI2()
                refineSubD = self.readF4()
                refineCrvs = self.readF4()
                sclPivot = self.readVEC12()
                for i in range(6):
                    unused = self.readU4()
                itemReference = self.readU4()
                refineSplPtch = self.readU2()
                for i in range(4):
                    unused = self.readU2()
                CCrenderlvl = self.readU2()
                CCpreviewlvl = self.readU2()
                subDrenderlvl = self.readU2()
                blobsize = chunkSize - (sizeSnap - self.modSize)
                blob = self.readblob(blobsize)
                # add layer to lxoFile
                # TODO: add all properties to layer
                currentLayer = lxoFile.addLayer(name, refineSubD,
                                                CCpreviewlvl,
                                                itemReference)
                if DEBUG:
                    print("", name, itemReference)
            elif chunkID == 'POLS':
                polyType = self.readID4()
                if polyType in ['SUBD', 'PSUB']:
                    currentLayer.isSubD = True
                # TODO figure this out
                if True:  # polyType in['FACE', 'SUBD', 'PSUB']:
                    polyCount = 0
                    while (sizeSnap - self.modSize) < chunkSize:
                        # TODO make this proper code
                        vertCount = self.readU2()
                        polyPoints = []
                        for i in range(vertCount):
                            vertIndex = self.readVX()
                            polyPoints.append(vertIndex)
                        currentLayer.polygons.append(polyPoints)
                    currentLayer.polyCount += polyCount
                else:
                    blobsize = chunkSize - (sizeSnap - self.modSize)
                    polygons = self.readblob(blobsize)
                if DEBUG:
                    print(polyType, polyCount)
            elif chunkID == 'PNTS':
                points = []
                while (sizeSnap - self.modSize) < chunkSize:
                    points.append(self.readVEC12())
                currentLayer.points = points
                if DEBUG:
                    print(len(points))
            elif chunkID == 'VMAP':
                mapType = self.readID4()
                dimension = self.readU2()
                name = self.readS0()
                values = {}
                while (sizeSnap - self.modSize) < chunkSize:
                    index = self.readVX()
                    vv = []
                    for val in range(dimension):
                        vv.append(self.readFloat())
                    values[index] = vv
                if mapType == 'TXUV':
                    currentLayer.uvMaps[name] = values
                if DEBUG:
                    print(mapType, dimension, name, len(values))
            elif chunkID == 'VMAD':
                mapType = self.readID4()
                dimension = self.readU2()
                name = self.readS0()
                values = {}
                while (sizeSnap - self.modSize) < chunkSize:
                    vertIndex = self.readVX()
                    polyIndex = self.readVX()
                    vv = []
                    for val in range(dimension):
                        vv.append(self.readFloat())
                    if polyIndex in values:
                        values[polyIndex][vertIndex] = vv
                    else:
                        values[polyIndex] = {vertIndex: vv}
                if mapType == 'TXUV':
                    currentLayer.uvMapsDisco[name] = values
                if DEBUG:
                    print(mapType, dimension, name, len(values))
            elif chunkID == 'PTAG':
                # MATR, PART, PICK, FONT, JUST, TEXT, SMGP
                tagType = self.readID4()
                ptags = []
                while (sizeSnap - self.modSize) < chunkSize:
                    polsIndex = self.readVX()
                    tagsIndex = self.readU2()
                    ptags.append((polsIndex, tagsIndex))
                currentLayer.ptags[tagType] = ptags
                if DEBUG:
                    print(tagType, ptags)
            elif chunkID == 'ENVL':
                index = self.readVX()
                type = self.readU4()
                blobsize = chunkSize - (sizeSnap - self.modSize)
                subchunks = self.readblob(blobsize)  # TODO
                if DEBUG:
                    print(index, type)
            elif chunkID == 'BBOX':
                minXYZ = self.readVEC12()
                maxXYZ = self.readVEC12()
                if DEBUG:
                    print(minXYZ, maxXYZ)
            elif chunkID == 'ITEM':
                typename = self.readS0()
                name = self.readS0()
                referenceID = self.readU4()
                item = lxoFile.addItem(name, referenceID, typename)

                if DEBUG:
                    print(typename, name, referenceID)

                while (sizeSnap - self.modSize) < chunkSize:
                    subchunkID = self.readID4()
                    subchunkSize = self.readU2()
                    subsizeSnap = self.modSize

                    # only read the tags specified
                    if (self.tagsToRead and
                            chunkID + subchunkID not in self.tagsToRead):
                        self.modSize -= subchunkSize
                        self.file.seek(subchunkSize, 1)
                        continue

                    if DEBUG:
                        print("", colored(subchunkID, 'yellow'), end=" ")

                    if subchunkID == 'PAKG':
                        packageName = self.readS0()
                        reserved = self.readU4()
                        item.packages.append(packageName)
                        if DEBUG:
                            print(packageName, reserved)
                    elif subchunkID == 'XREF':
                        indexSubScene = self.readU4()
                        filename = self.readS0()
                        itemId = self.readS0()
                        if DEBUG:
                            print(indexSubScene, filename, itemId)
                    elif subchunkID == 'LAYR':
                        index = self.readU4()
                        flags = self.readU4()
                        rgbs = self.readU14()
                        item.LAYR = (index, flags, rgbs)
                        if DEBUG:
                            print(index, flags, rgbs)
                    elif subchunkID == 'LINK':
                        graphname = self.readS0()
                        itemIndex = self.readI4()
                        linkIndex = self.readI4()
                        item.graphLinks[graphname] = (itemIndex, linkIndex)
                        if DEBUG:
                            print(graphname, itemIndex, linkIndex)
                    elif subchunkID == 'CHNL':
                        name = self.readS0()
                        datatype = self.readU2()
                        value = self.readValue(datatype)
                        item.CHNL.append((name, datatype, value))
                        if DEBUG:
                            print(name, datatype, value)
                    elif False and subchunkID == 'GRAD':
                        # TODO:
                        blobsize = subchunkSize - (subsizeSnap - self.modSize)
                        blob = self.readblob(blobsize)
                        item.GRAD.append(blob)
                    elif False and subchunkID == 'CLNK':
                        # TODO:
                        blobsize = subchunkSize - (subsizeSnap - self.modSize)
                        blob = self.readblob(blobsize)
                        item.CLNK.append(blob)
                    elif False and subchunkID == 'UCHN':
                        # TODO:
                        blobsize = subchunkSize - (subsizeSnap - self.modSize)
                        blob = self.readblob(blobsize)
                        item.CLNK.append(blob)
                    elif subchunkID == 'CHNS':
                        name = self.readS0()
                        value = self.readS0()
                        item.channel[name] = value
                        if DEBUG:
                            print(name, value)
                    elif subchunkID == 'CHAN':
                        index = self.readVX()
                        datatype = self.readU2()
                        value = self.readValue(datatype)
                        item.channel[lxoFile.channelNames[index]] = value
                        if DEBUG:
                            print(lxoFile.channelNames[index], datatype, value)
                    elif subchunkID == 'CHNV':
                        name = self.readS0()
                        datatype = self.readU2()
                        vectorcount = self.readU2()
                        vec = []
                        for i in range(vectorcount):
                            cname = self.readS0()
                            value = self.readValue(datatype)
                            vec.append((cname, value))
                        item.CHNV[name] = vec  # datatype?
                        if DEBUG:
                            print(name, vec)
                    elif subchunkID == 'ITAG':
                        type = self.readID4()
                        value = self.readS0()
                        item.itemTags.append((type, value))
                        if DEBUG:
                            print(type, value)
                    elif subchunkID == 'VNAM':
                        name = self.readS0()
                        item.vname = name
                        if DEBUG:
                            print(name)
                    elif subchunkID == 'UNIQ':
                        identifier = self.readS0()
                        if DEBUG:
                            print(identifier)
                    elif subchunkID == 'UIDX':
                        index = self.readU4()
                        if DEBUG:
                            print(index)
                    elif subchunkID == 'CHNC':
                        size = self.readU2()
                        data = ""
                        for i in range(size):
                            data += self.readU1()
                        item.CHNC.append(data)
                        if size % 2:
                            # if uneven length read one more byte
                            self.readU1()
                        if DEBUG:
                            print(data)
                    elif subchunkID == 'BCHN':
                        operationType = self.readS0()
                        data = self.readU4()
                        if DEBUG:
                            print(operationType, data)
                    else:
                        blobsize = subchunkSize - (subsizeSnap - self.modSize)
                        blob = self.readblob(blobsize)
                        if DEBUG:
                            print(colored("BLOB", "red"), blob)
            elif chunkID == 'ACTN':  # action layers: edit, scene, setup
                self.__readACTN(lxoFile, sizeSnap, chunkSize)
            else:
                self.modSize -= chunkSize
                self.file.seek(chunkSize, 1)  # skipping chunk
                if DEBUG:
                    print(colored("BLOB skipped", "red"))

    def __readACTN(self, lxoFile, sizeSnap, chunkSize):
        actionlayername = self.readS0()
        actionlayertype = self.readS0()
        actionlayerindex = self.readU4()
        actionLayer = lxoFile.addActionLayer(actionlayername,
                                             actionlayertype,
                                             actionlayerindex)
        currentActionItem = None

        if DEBUG:
            print(actionlayername, actionlayertype, actionlayerindex)

        while (sizeSnap - self.modSize) < chunkSize:
            subchunkID = self.readID4()
            subchunkSize = self.readU2()
            subsizeSnap = self.modSize

            if (self.tagsToRead and
                    chunkID + subchunkID not in self.tagsToRead):
                self.modSize -= subchunkSize
                self.file.seek(subchunkSize, 1)
                continue

            if DEBUG:
                print("", colored(subchunkID, 'yellow'), end=" ")

            if subchunkID == 'ITEM':
                itemReferenceID = self.readU4()
                currentActionItem = actionLayer.addItem(itemReferenceID)
                if DEBUG:
                    print(itemReferenceID)
            elif subchunkID == 'CHAN':
                index = self.readVX()
                datatype = self.readU2()
                indexENVL = self.readVX()
                value = self.readValue(datatype)
                data = (lxoFile.channelNames[index], datatype, indexENVL,
                        value)
                currentActionItem.CHAN.append(data)
                if DEBUG:
                    print(lxoFile.channelNames[index], datatype,
                          indexENVL, value)
            elif subchunkID == 'GRAD':
                # TODO:
                blobsize = subchunkSize - (subsizeSnap - self.modSize)
                blob = self.readblob(blobsize)
                currentActionItem.GRAD.append(blob)
                if DEBUG:
                    print(blob)
            elif subchunkID == 'CHNS':
                name = self.readS0()
                index = self.readVX()
                value = self.readS0()
                data = (name, lxoFile.channelNames[index], value)
                currentActionItem.stringChannels.append(data)
                if DEBUG:
                    print(lxoFile.channelNames[index], value, name)
            else:
                # TODO figure out what PRNT subchunk is for
                blobsize = subchunkSize - (subsizeSnap - self.modSize)
                blob = self.readblob(blobsize)
                if DEBUG:
                    print(colored("BLOB", "red"), blob)


if __name__ == '__main__':
    desc = 'Read (specific) stuff from LXO.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("sourceFile", help="source FILE", metavar="FILE")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-P", "--prettyPrint", action="store_true")

    args = parser.parse_args()
    if args.debug:
        print('enabled DEBUG print')
        DEBUG = True

    lxoRead = LXOReader()
    # lxoRead.tagsToRead = []

    lxo = lxoRead.readFromFile(args.sourceFile)

    if args.prettyPrint:
        print('### pprint ###')
        lxo.pprint()
