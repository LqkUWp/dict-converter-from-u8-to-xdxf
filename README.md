# dict-converter-from-u8-to-xdxf
adapt https://github.com/k-sl/CedictXML to python3 and compile it to win10-64bit .exe via cython. all commands following run correctly on my win10-64bit pc with `Python 3.8.2` and `MinGW-W64-builds-4.3.5`. 

# usage
you only need the `.exe` to convert `.u8` dictionary to `.xdxf` format without any other dependency. usage is similar with https://github.com/k-sl/CedictXML. 
```
# generate ./CC-CEDICT_<date>-1.2.xdxf via example.u8
u8_to_xdxf.exe -i example.u8

# generate example.xdxf via example.u8
u8_to_xdxf.exe -i example.u8 -o example.xdxf

# download the latest .u8 dict from https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip and convert it to .xdxf format in the current path. you can also manually download the latest .u8 dict from https://www.mdbg.net/chinese/dictionary?page=cc-cedict. 
u8_to_xdxf.exe -d
```

# how are these files generated

## .py
generated by mixing `cedictxml.py` and `pinyin.py` in https://github.com/k-sl/CedictXML. in addition, it's modified some format to adapt python3 and inserted a line at the beginning
```
# cython: language_level=3
``` 

## .c
generated via
```
cython --embed -o u8_to_xdxf.c u8_to_xdxf.py
```
`--embed` will prevent the warning `` undefined reference to `wWinMain` `` when compiling this .c file. 

## .exe
generated via
```
gcc -municode -DMS_WIN64 -Ofast -I "D:\Python\include" -L "D:\Python\libs" -o u8_to_xdxf.exe u8_to_xdxf.c -l python38
```
where all options but `-Ofast` are required. 
