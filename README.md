# lxoReader
LXO reader writtern in python. More information about the file format can be found here:
https://modosdk.foundry.com/wiki/File_Formats

This reader allows to specify chunks to be read, which increases reading speed significantly in various cases. I started this a means to e.g. read filenames stored in an LXO file. It also allows to run basic checks without the overhead of starting Modo.

### Examples
Usage as command line tool: Output all chunks and subchunks

```
./lxoReader.py <filepath> -d
```

Usage as python module
```python
import lxoReader

# create Reader object
lxoRead = lxoReader.LXOReader()
# define chunks to read
lxoRead.tagsToRead = ['ITEM']

# read file
# filepath has to be a vaild filepath
lxo = lxoRead.readFromFile(filepath)

# print name and type
for item in lxo.items:
    name = item.name if item.name else item.vname
    print(name, item.typename)

# read some of the mesh data chunks
lxoRead.tagsToRead = ['LAYR', 'POLS', 'PNTS']

lxo = lxoRead.readFromFile(filepath)
for layer in lxo.layers:
    print(layer.polyCount, layer.vertCount)


# read filenames stored in file, usually with textures
# they are string channels in the ITEM chunk
# to read subchunks, they are added to the chunk they are contained in
lxoRead.tagsToRead = ['ITEM', 'ITEMCHNS']

lxo = lxoRead.readFromFile(filepath)

for item in lxo.items:
    if "filename" in item.channel:
        print(item.typename, item.channel["filename"])
```
