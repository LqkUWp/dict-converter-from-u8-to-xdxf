#!/usr/bin/env python
# -*- coding: utf-8 -*-
# https://github.com/k-sl/CedictXML
# cython: language_level=3

from io import open
from re import findall,escape,compile,I
from time import strftime,localtime
from argparse import ArgumentParser
from zipfile import ZipFile
from urllib.request import urlopen
from tempfile import TemporaryFile
from tqdm import tqdm
from lxml import etree as ET

def pinyinize(src, raise_exception=False):
    "Turns a source string like 'ni3 hao3' into a utf-8 equivalent with tone marks"

    try:
        def replacer(m):
            syllable, pre, vowels, post, tone = m.groups()
            vowels = list(vowels)
            if ':' in vowels:
                dot_dot_index = vowels.index(':')
                vowels[dot_dot_index - 1] += vowels[dot_dot_index]
                del vowels[dot_dot_index]

            if syllable.lower() == 'r' and tone == '5':
                return syllable

            tone = int(tone)

            v = [c.lower() for c in vowels]
            # 3 rules
            # 1- A and E get the tone mark if either one present (they are never both present)
            # 2- in ou, o gets the tone mark
            # 3- in all other cases, last vowel gets the tone
            # see http://pinyin.info/rules/where.html

            # rule 1
            if 'a' in v:
                tindex = v.index('a')
            elif 'e' in v:
                tindex = v.index('e')
            elif 'ou' == v: # rule 2
                tindex = 0
            else: # rule 3
                tindex = len(v) - 1


            try:
                vowels = [v for v in vowels]
                vowels[tindex] = TONE_MARKS[vowels[tindex]][tone]

                vowels = [v if ':' not in v else TONE_MARKS[v][5] for v in vowels]

                vowels = u''.join(vowels)
                return "%s%s%s" % (pre, vowels, post)
            except:
#                import sys
#                import traceback
#                typ, err, tb = sys.exc_info()
#                traceback.print_tb(tb)
#                print typ, err
                if raise_exception:
                    raise
                return m.group(0)

        return PINYIN_RE.sub(replacer, src)
    except:
#        import sys
#        import traceback
#        typ, err, tb = sys.exc_info()
#        traceback.print_tb(tb)
#        print typ, err, 'src=', repr(src)
        if raise_exception:
            raise

        return src

def depinyinize(src):
    "Turns a source string like 'nǐ hǎo' into 'ni3 hao3'"

    unmarked = {}
    for k, v in TONE_MARKS.items():
        for i, c in enumerate(v[1:5]):
            unmarked[c] = (k, i+1)


    newstr = []
    lc = src.lower()
    i = 0
    while i < len(src):
        c = src[i]

        # see if this is a character with a tone mark
        if c in unmarked:
            letter, tone = unmarked[c]

            # find every sound that includes this vowel
            possible_sounds = [s for s in ALL_SOUNDS if letter.lower() in s]

            #try and match longest sounds first
            possible_sounds.sort(key=len)
            possible_sounds.reverse()

            sound = None
            so_far = u''.join(newstr).lower()
            for p in possible_sounds:
                li = p.find(letter.lower())
                before_match, after_match = p[:li], p[li+len(letter):]

                # see if this sound's spelling matches what we have...
                if ((len(before_match) == 0 # either there's nothing before the match
                    or so_far[-len(before_match):] == before_match) # or the bit before the match is in our string
                    and # ... AND
                    # the bit after the match is 0 or matches our string
                   (len(after_match) == 0 or lc[i+1:len(after_match)+i+1] == after_match)):
                    sound = p
                    break
            if sound:

                newstr.append(letter)
                # preserve case, use chars from original string
                newstr += list(src[i+1:len(after_match)+i+1])
                newstr.append(u'%d' % tone)
                i += len(after_match) + 1
            else:
                newstr.append(letter)
                i += 1

        else: # no tone mark, check for neutral tone ü
            if c == TONE_MARKS['U:'][5]:
                newstr.append('U:')
            elif c == TONE_MARKS['u:'][5]:
                newstr.append('u:')
            else:
                newstr.append(c)
            i += 1

    return u''.join(newstr)

def download_cedict():
    tempzip = TemporaryFile()
    url = urlopen(file_url)
    tempzip.write(url.read())
    zipped_cedict = ZipFile(tempzip, 'r')
    temptxt = TemporaryFile()
    temptxt = zipped_cedict.open("cedict_ts.u8", "r").read()
    zipped_cedict.close()
    return temptxt.decode('utf8')

def pyjoin(pinyinsyllables):
    """Convert CEDICT-style pinyin notation to correct pinyin.

    Converts the CC-CEDICT-style space-separated pinyin syllables to
    correct pinyin with tone marks and apostrophes.
    (Information about which syllables take a apostrophes after
    pinyin.info.)
    """
    # Tuple of letters after which an apostrophe is needed:
    apletters = (u"ā", u"á", u"ǎ", u"à", u"a", u"ē", u"é", u"ě", u"è", u"e",
                 u"ō", u"ó", u"ǒ", u"ò", u"o")
    # "r5" is a mistake, 儿 when transcribed as "r" is not a syllable,
    # it cannot have a tone.
    pinyinsyllables = pinyinsyllables.replace("r5", "r")
    pinyinsyllables = pinyinize(pinyinsyllables)
    # Add apostrophe when appropriate:
    syllablelist = pinyinsyllables.split()
    if len(syllablelist) > 1:
        relevantsyl = syllablelist[1:]
        for i in range(len(relevantsyl)):
            if relevantsyl[i].startswith(apletters):
                relevantsyl[i] = u"'" + relevantsyl[i]
        finallist = syllablelist[:1] + relevantsyl[:]
        finalword = "".join(finallist)
    else:
        finalword = "".join(syllablelist)
    # In case the pinyin syllable belongs to a foreign name and is
    # preceded by "·", the apostrophe is not needed (and simply wrong).
    finalword = finalword.replace(u"·'",u"·")
    # In case there is a capital letter in middle of a word there
    # should be a space before it. (It's likely a several-word place
    # name.)
    if u"·" not in finalword:
        needsspace = findall(u".+?([A-Z]|Ā|Á|Ǎ|À|Ē|É|Ě|È|Ī|Í|Ǐ|Ì|Ō|Ó|Ǒ|Ò|Ū"
                                u"|Ú|Ǔ|Ù).+?", finalword)
        if needsspace is not []:
            for item in needsspace:
                finalword = finalword.replace(item, " " + item)
    return finalword

def bracketpy(pystring):
    """Find CEDICT-style pinyin in square brackets and correct pinyin.

    Looks for square brackets in the string and tries to convert its
    contents to correct pinyin. It is assumed anything in square
    brackets is CC-CEDICT-format pinyin.

    e.g.: "拼音[pin1 yin1]" will be converted into "拼音 pīnyīn".
    """
    if len(findall("(\[.+?\])", pystring)) >= 1:
        cedpylist = findall("(\[.+?\])", pystring)
        for item in cedpylist:
            pystring = pystring.replace(item, " " + pyjoin(item[1:-1]))
        return pystring
    if len(findall("(\[.+?\])", pystring)) < 1:
        return pystring
    else:
        return None

def dictconvert(dictionaryfile):
    """Convert a CC-CEDICT file string into a python dictionary.

    The CC-CEDICT dictionary string is converted into a python dictionary,
    itself consisting of dictionaries. The main dictionary, cedict_dict,
    includes a dictionary with the key "header" and the header of the
    CC-CEDICT file as key, plus as many dictionaries as entries in the
    CC-CEDICT dictionary with the number of the line they appear in as
    key and dictionaries containing the parsed information for each
    entry as follows:

    Dictionary structure:

    cedict_dict (dictionaries)
     |- header (string)
     |- linenum (dictionaries)
            |- entry_jian (string)
            |- entry_fan (string)
            |- entry_pinyin (string)
            |- entry_translation (list of strings)
            |- entry_measureword (list, optional)
            |- entry_taiwan (string, optional)

    header: the header of the CC-CEDICT file. (From the first line, all
        lines starting with "#".)
    linenum: number of the line of the entry on the CC-CEDICT file.
    entry_jian: The Chinese word/phrase in simplified Chinese.
    entry_taiwan: The Chinese word/phrase in traditional Chinese.
    entry_translation: A list of strings, each being a definition of
        the Chinese word/phrase.
    entry_measureword: list of one or more measure words
        (classifiers) related to the Chinese word/phrase.
    """
    linenum = int(0)
    header = str()
    for line in tqdm(dictionaryfile.split("\n")):
        linenum = linenum + 1
        # So that if something goes wrong we know which line is causing the
        # problem:
        try:
            # Get the header.
            if line.startswith("#"):
                header = header + line[2:]
            else:
                # Get the four main parts of each entry.
                entry_fan = findall("^(.+?) ", line)[0]
                entry_jian = findall("^.+? (.+?) ", line)[0]
                entry_pinyin = pyjoin(findall(".+ \[(.+?)\] ", line)[0])
                entry_translation = findall(".+ (\/.+\/)", line)[0]
                # Get the measure words and delete them from the translation.
                if len(findall("CL:(.+?])\/", entry_translation)) == 0:
                    entry_measureword = ""
                if len(findall("CL:(.+?])\/", entry_translation)) > 0:
                    cl_list = entry_measureword = findall("CL:(.+?])\/",
                                                            entry_translation)
                    entry_measureword = cl_list[0]
                    if len(cl_list) > 1:
                        for cl in cl_list[1:]:
                            entry_measureword = entry_measureword + " " + cl
                    for cl in cl_list:
                        entry_translation = entry_translation.replace("CL:"
                                                                     + cl, "")
                    # Correct pinyin in measure words and convert into list.
                    entry_measureword = bracketpy(entry_measureword)
                    entry_measureword = entry_measureword.split(",")
                # Get Taiwan pronunciation and delete it from the translation.
                if len(findall("Taiwan pr\. \[(.+?)\]",
                      entry_translation)) == 0:
                    entry_taiwan = ""
                if len(findall("Taiwan pr\. \[(.+?)\]",
                      entry_translation)) > 1:
                    print ("\nAn error occurred while parsing the Taiwan "
                          "pronunciation for line %s. This line was "
                          "ignored." % str(linenum))
                    print ("    Line", str(linenum) + ":", line)
                if len(findall("Taiwan pr\. \[(.+?)\]",
                      entry_translation)) == 1:
                    entry_taiwan = (findall("Taiwan pr\. \[(.+?)\]",
                                   entry_translation)[0])
                    entry_translation = (entry_translation.replace
                                        ("Taiwan pr. [" + entry_taiwan +
                                        "]", ""))
                    entry_taiwan = pyjoin(entry_taiwan)
                # Correct three dots to ellipsis.
                entry_translation = entry_translation.replace(u"...", u"…")
                # Correct the pinyin and separate the different translations
                # into a list.
                entry_translation = bracketpy(entry_translation)
                entry_translation = entry_translation.split("/")
                entry_translation = filter(None, entry_translation)
                # Create final dictinary object with all basic entries.
                cedict_dict[linenum] = ({"entry_jian": entry_jian,
                                      "entry_fan" : entry_fan,
                                      "entry_pinyin" : entry_pinyin,
                                      "entry_translation" :
                                      entry_translation})
                # Add Taiwan pronunciation and measure word when they exist.
                if entry_taiwan != "":
                    cedict_dict[linenum]["entry_taiwan"] = entry_taiwan
                if entry_measureword != "":
                    (cedict_dict[linenum]
                    ["entry_measureword"]) = entry_measureword
        except:
            print ("Line %s was not understood and was ignored."
                  % linenum)
            print ("Line", str(linenum) + ":", line)
            continue
    cedict_dict["header"] = header
    date_pos = header.find("date=")
    global publishing_date
    publishing_date = header[date_pos+5:date_pos+15]
    global publishing_date_xdxf
    publishing_date_xdxf = (publishing_date[8:] + "-" +
                           publishing_date[5:7] + "-" + publishing_date[:5])
    global dictionary_version
    dictionary_version = publishing_date.replace("-","") + "-" + version
    return cedict_dict

def createxdxf(dictionary):
    """Convert the dictionary object into a valid XDXF-format string.

    Takes a dictionary in the format provided by dictconvert and
    returns a string with the whole dictionary content in xml format
    following the XDXF standard as described in
    https://github.com/soshial/xdxf_makedict/blob/master/format_standard/xdxf_description.md
    """
    # List of abbreviations in the dictionary:
    abbreviations = [("Budd.", "Buddhism", "knl"), ("Cant.", "Cantonese",
                    "oth"), ("cf", "confer, ‘compare’", "aux"), ("Dept.",
                    "Department", ""), ("P.R.C.", "People's Republic of China",
                    ""), ("TCM", "Traditional Chinese Medicine", "knl"), ("Tw",
                    "Taiwan", ""), ("U.S.", "United States of America", ""),
                    ("Univ.", "University", ""), ("a.k.a.", "also known as",
                    "aux"), ("abbr.", "abbreviation", "aux"), ("adj.",
                    "adjective", ""), ("agr.", "agriculture", "knl"), ("arch.",
                    "archaic", "stl"), ("astron.", "astronomy", "knl"),
                    ("auto.", "automobile", ""), ("biol.", "biology", "knl"),
                    ("c.", "circa", "aux"), ("cm.", "centimetre", ""),
                    ("coll.", "colloquial", "stl"), ("derog.", "derogatory",
                    "stl"), ("dial.", "dialect", "stl"), ("e.g.",
                    "exempli gratia, ‘for example’", "aux"), ("elec.",
                    "electricity", "knl"), ("electric.", "electricity",
                    "knl"), ("esp.", "especially", "aux"), ("euph.",
                    "euphemism", "stl"), ("expr.", "expression", "aux"),
                    ("ext.", "extension", "aux"), ("fig.", "figuratively",
                    "aux"), ("geom.", "geometry", "knl"), ("gov.",
                    "government", ""), ("hist.", "history", "knl"), ("i.e.",
                    "id est, ‘that is’", "aux"), ("in.", "inches", ""),
                    ("incl.", "including", "aux"), ("interj.", "interjection",
                    "grm"), ("lab.", "laboratory", ""), ("ling.",
                    "linguistic", "knl"), ("lit.", "literally", "aux"),
                    ("math.", "mathematics", "knl"), ("med.", "medicine",
                    "knl"), ("mus. instr.", "musical instrument", ""),
                    ("myth.", "mythology", "knl"), ("onom.", "onomatopoeia",
                    "grm"), ("onomat.", "onomatopoeia", "grm"), ("orig.",
                    "originally", ""), ("pathol.", "pathology", "knl"),
                    ("pharm.", "pharmacology", "knl"), ("pr.", "pronunciation",
                    "aux"), ("psych.", "psychology", "knl"), ("punct.",
                    "punctuation", "knl"), ("stats.", "statistics", "knl"),
                    ("telecom.", "telecommunications", "knl"), ("trad.",
                    "traditional(ly)","stl"), ("translit.", "transliteration",
                    "aux"), ("usu.", "usually", "aux"), ("zool.", "zoology",
                    "knl"), ("zoolog.", "zoology", "knl"), ("sth", "something",
                    "aux"), ("sb", "somebody", "aux")]
    abbrlist = []
    for tupple in abbreviations:
        abbrlist.append(tupple[0])
    # Get the description from the original header and add information about
    # the conversion.
    conversion_info = ("_lb_This XDXF file was created automatically by the "
                      "CedictXML converter, version %s on %s._lb_CedictXML "
                      "is free and unencumbered software released into the "
                      "public domain." % (version, currenttime))
    description = dictionary["header"].replace("\n","_lb_") + conversion_info
    xdxfdic_top = ET.Element("xdxf", lang_from="CHI", lang_to="ENG",
                            format="logical", revision="33")
    # Header is no longer needed, only dictionary entries should be left.
    del dictionary["header"]
    meta_info = ET.SubElement(xdxfdic_top, "meta_info")
    lexicon = ET.SubElement(xdxfdic_top, "lexicon")
    meta_info_title = ET.SubElement(meta_info, "title").text = dictionaryname
    meta_info_full_title = ET.SubElement(meta_info,
                                        "full_title").text = dictionaryname
    meta_info_publisher = ET.SubElement(meta_info, "publisher").text = "MDBG"
    meta_info_description = ET.SubElement(meta_info,
                                         "description").text = description
    meta_info_abbreviations = ET.SubElement(meta_info, "abbreviations")
    for abbreviation in abbreviations:
        if abbreviation[2] != "":
            current_abbr_def = ET.SubElement(meta_info_abbreviations,
                                            "abbr_def", type=abbreviation[2])
            abbr_k = ET.SubElement(current_abbr_def,
                                  "abbr_k").text = abbreviation[0]
            abbr_v = ET.SubElement(current_abbr_def,
                                  "abbr_v").text = (abbreviation[1])
        else:
            current_abbr_def = ET.SubElement(meta_info_abbreviations,
                                            "abbr_def")
            abbr_k = ET.SubElement(current_abbr_def,
                                  "abbr_k").text = abbreviation[0]
            abbr_v = ET.SubElement(current_abbr_def,
                                  "abbr_v").text = abbreviation[1]
    meta_info_file_ver = ET.SubElement(meta_info,
                                      "file_ver").text = (dictionary_version +
                                                         "-" + version)
    meta_info_creation_date = ET.SubElement(meta_info,
                                           "creation_date").text = (currenttime
                                                                   [:10])
    meta_info_publishing_date = (ET.SubElement
                                (meta_info,"publishing_date").text) = (publishing_date_xdxf)
    meta_info_dict_src_url = ET.SubElement(meta_info,
                                          "dict_src_url").text = src_url
    for key,value in tqdm(dictionary.items()):
        lexicon_ar = ET.SubElement(lexicon, "ar")
        lexicon_ar_k = ET.SubElement(lexicon_ar, "k").text = value["entry_jian"]
        lexicon_ar_k_trad = ET.SubElement(lexicon_ar,
                                         "k").text = value["entry_fan"]
        lexicon_ar_def = ET.SubElement(lexicon_ar, "def")
        lexicon_ar_def_grtr = ET.SubElement(lexicon_ar_def, "gr")
        lexicon_ar_def_grtr_tr = ET.SubElement(lexicon_ar_def_grtr,
                                              "tr").text = value["entry_pinyin"]
        if value.get("entry_taiwan") is not None:
            lexicon_ar_def_grtr_gr_tw = ET.SubElement(lexicon_ar_def, "gr")
            lexicon_ar_def_grtr_tr_tw = ET.SubElement(lexicon_ar_def_grtr_gr_tw,
                                                     "tr").text = value["entry_taiwan"]
        if value.get("entry_measureword") is not None:
            # Reassemble the measure words into a string.
            measurewords = "Measure words:"
            for item in value["entry_measureword"]:
                measurewords = measurewords + " " + item
            lexicon_ar_def_mw = ET.SubElement(lexicon_ar_def,
                                             "gr").text = measurewords
        for translation in value["entry_translation"]:
            lexicon_ar_def_def = ET.SubElement(lexicon_ar_def, "def")
            # Recognize the abbreviations.
            for abbreviation in abbrlist:
                abbreviation_re = r"\b(" + escape(abbreviation) + r")\W|\b(" + escape(abbreviation) + r")$"
                if len(findall(abbreviation_re,translation)) > 0:
                    translation = (translation.
                                  replace(abbreviation, "_lt_abbr_mt_" +
                                  abbreviation + "_lt_/abbr_mt_"))
            # Recognize intra-dictionary references.
            if findall("[Ss]ee ([^\x00-\x7F]+?)[\| \)\.]",
                         translation) is not []:
                for item in findall("[Ss]ee ([^\x00-\x7F]+?)[\| \)\.]",
                                      translation):
                    translation = translation.replace(item,
                                                     "_lt_kref_mt_" + item +
                                                     "_lt_/kref_mt_")
            if findall("[Ss]ee also ([^\x00-\x7F]+?)[\| \)\.]",
                         translation) is not []:
                for item in findall("[Ss]ee also ([^\x00-\x7F]+?)[\| \)\.]",
                                      translation):
                    translation = (translation.
                                  replace(item, "_lt_kref_mt_" + item +
                                  "_lt_/kref_mt_"))
            if findall("[Vv]ariant of ([^\x00-\x7F]+?)[\| \)\.]",
                         translation) is not []:
                for item in findall("[Vv]ariant of ([^\x00-\x7F]+?)[\| \)\.]",
                                      translation):
                    translation = translation.replace(item, "_lt_kref_mt_" +
                                                     item + "_lt_/kref_mt_")
            # Recognize external links. Protocol is assumed to be HTTP.
            if "Planck's constant" not in translation:
                if len(findall(r"\b([a-zA-Z]{2,}?\.[a-zA-Z0-9][a-zA-Z0-9._]"
                                 "{2,})\b", translation)) > 0:
                    for item in findall(r"\b([a-zA-Z]{2,}?\.[a-zA-Z0-9]"
                                          "[a-zA-Z0-9._]{2,})\b", translation):
                        translation = (translation.
                                      replace(item, "_lt_iref href=\"http://" +
                                      item + "\"_mt_" + item + "_lt_/iref_mt_"))
            lexicon_ar_def_def_deftext = (ET.SubElement
                                         (lexicon_ar_def_def,
                                         "deftext").text) = translation
    return xdxfdic_top

def multi_replace(inputstring, replacements):
    """Apply the replace method multiple times.

    "inputstring" is self-explanatory, "replacements" is a list of
    tuples, the fist item of each tuple the substring to be replaced
    and the second the replacement text.
    """
    for replacement in replacements:
        inputstring = inputstring.replace(replacement[0], replacement[1])
    return inputstring

if __name__=='__main__':

    PINYIN_RE = compile(r'(([bcdfghjklmnpqrstwxyz]*)(u:an|u:|u:e|[aeiou]+)([bcdfghjklmnpqrstwxyz]*)|r)([1-5])', I)
    
    TONE_MARKS = {
        'a':u'_āáǎàa',
        'e':u'_ēéěèe',
        'i':u'_īíǐìi',
        'o':u'_ōóǒòo',
        'u':u'_ūúǔùu',
        'u:':u'_ǖǘǚǜü'
    }
    
    # use upper() to get the upper case versions
    TONE_MARKS['A'] = TONE_MARKS['a'].upper()
    TONE_MARKS['E'] = TONE_MARKS['e'].upper()
    TONE_MARKS['I'] = TONE_MARKS['i'].upper()
    TONE_MARKS['O'] = TONE_MARKS['o'].upper()
    TONE_MARKS['U'] = TONE_MARKS['u'].upper()
    TONE_MARKS['U:'] = TONE_MARKS['u:'].upper()
    
    ALL_SOUNDS = set(['a', 'ai', 'an', 'ang', 'ao', 'ba', 'bai', 'ban', 'bang',
        'bao', 'bei', 'ben', 'beng', 'bi', 'bian', 'biao', 'bie', 'bin', 'bing',
        'bo', 'bu', 'ca', 'cai', 'can', 'cang', 'cao', 'ce', 'cen', 'ceng', 'cha',
        'chai', 'chan', 'chang', 'chao', 'che', 'chen', 'cheng', 'chi', 'chong',
        'chou', 'chu', 'chuai', 'chuan', 'chuang', 'chui', 'chun', 'chuo', 'ci',
        'cong', 'cou', 'cu', 'cuan', 'cui', 'cun', 'cuo', 'da', 'dai', 'dan',
        'dang', 'dao', 'de', 'dei', 'den', 'deng', 'di', 'dian', 'diao', 'die',
        'ding', 'diu', 'dong', 'dou', 'du', 'duan', 'dui', 'dun', 'duo', 'e', 'en',
        'er', 'fa', 'fan', 'fang', 'fei', 'fen', 'feng', 'fo', 'fou', 'fu', 'ga',
        'gai', 'gan', 'gang', 'gao', 'ge', 'gei', 'gen', 'geng', 'gong', 'gou',
        'gu', 'gua', 'guai', 'guan', 'guang', 'gui', 'gun', 'guo', 'ha', 'hai',
        'han', 'hang', 'hao', 'he', 'hei', 'hen', 'heng', 'hong', 'hou', 'hu',
        'hua', 'huai', 'huan', 'huang', 'hui', 'hun', 'huo', 'ji', 'jia', 'jian',
        'jiang', 'jiao', 'jie', 'jin', 'jing', 'jiong', 'jiu', 'ju', 'juan', 'jue',
        'jun', 'ka', 'kai', 'kan', 'kang', 'kao', 'ke', 'ken', 'keng', 'kong',
        'kou', 'ku', 'kua', 'kuai', 'kuan', 'kuang', 'kui', 'kun', 'kuo', 'la',
        'lai', 'lan', 'lang', 'lao', 'le', 'lei', 'leng', 'li', 'lia', 'lian',
        'liang', 'liao', 'lie', 'lin', 'ling', 'liu', 'long', 'lou', 'lu', 'luan',
        'lun', 'luo', 'lu:', 'lu:an', 'lu:e', 'ma', 'mai',     'man', 'mang', 'mao',
        'me', 'mei', 'men', 'meng', 'mi', 'mian', 'miao',     'mie', 'min', 'ming',
        'miou', 'mo', 'mou', 'mu', 'na', 'nai', 'nan',     'nang', 'nao', 'ne', 'nei',
        'nen', 'neng', 'ni', 'nian', 'niang', 'niao',     'nie', 'nin', 'ning', 'niu',
        'nong', 'nou', 'nu', 'nuan', 'nuo',     'nu:', 'nu:e', 'ou', 'pa', 'pai', 'pan',
        'pang', 'pao', 'pei', 'pen',     'peng', 'pi', 'pian', 'piao', 'pie', 'pin',
        'ping', 'po', 'pou', 'pu', 'qi',     'qia', 'qian', 'qiang', 'qiao', 'qie',
        'qin', 'qing', 'qiong', 'qiu', 'qu',     'quan', 'que', 'qun', 'r', 'ran',
        'rang', 'rao', 're', 'ren', 'reng', 'ri',     'rong', 'rou', 'ru', 'ruan',
        'rui', 'run', 'ruo', 'sa', 'sai', 'san',     'sang', 'sao', 'se', 'sen', 'seng',
        'sha', 'shai', 'shan', 'shang', 'shao',     'she', 'shei', 'shen', 'sheng',
        'shi', 'shou', 'shu', 'shua', 'shuai',     'shuan', 'shuang', 'shui', 'shun',
        'shuo', 'si', 'song', 'sou', 'su',     'suan', 'sui', 'sun', 'suo', 'ta', 'tai',
        'tan', 'tang', 'tao', 'te',     'teng', 'ti', 'tian', 'tiao', 'tie', 'ting',
        'tong', 'tou', 'tu', 'tuan',     'tui', 'tun', 'tuo', 'wa', 'wai', 'wan',
        'wang', 'wei', 'wen', 'weng', 'wo',     'wu', 'xi', 'xia', 'xian', 'xiang',
        'xiao', 'xie', 'xin', 'xing', 'xiong',     'xiu', 'xu', 'xuan', 'xue', 'xun',
        'ya', 'yan', 'yang', 'yao', 'ye', 'yi',     'yin', 'ying', 'yong', 'you', 'yu',
        'yuan', 'yue', 'yun', 'za', 'zai',     'zan', 'zang', 'zao', 'ze', 'zen',
        'zeng', 'zha', 'zhai', 'zhan', 'zhang',     'zhao', 'zhe', 'zhen', 'zheng',
        'zhi', 'zhong', 'zhou', 'zhu', 'zhua',     'zhuai', 'zhuan', 'zhuang', 'zhui',
        'zhun', 'zhuo', 'zi', 'zong', 'zou',     'zu', 'zuan', 'zui', 'zun', 'zuo'])

    version = "1.2"
    dictionaryname = "CC-CEDICT"
    currenttime = strftime("%d-%m-%Y %H:%M:%S", localtime())
    dtd_url = "https://raw.github.com/soshial/xdxf_makedict/master/format_standard/xdxf_strict.dtd"
    doctypestring = "<!DOCTYPE xdxf SYSTEM \'%s\'>" % dtd_url
    declaration = ("CedictXML: CC-CEDICT to XDXF Converter\nVersion %s\n" % version)
    header = ""
    src_url = "http://www.mdbg.net/chindict/chindict.php?page=cc-cedict"
    file_url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip"
    publishing_date = ""
    dictionary_version = ""
    cedict_dict = dict()    # Final dictionary object
    
    # Set and parse arguments.
    argparser = ArgumentParser()
    argparser.add_argument("-i", "--input-file", help="Original CC-CEDICT file to "
                                                    "be converted.")
    argparser.add_argument("-o", "--output-file", help="Resulting XDXF-format "
                                                    "file.")
    argparser.add_argument("-d", "--download", help="Download the most recent "
                                                    "release of CC-CEDICT and use "
                                                    "it as input file.",
                                                    action="store_true")
    args = argparser.parse_args()
    
    print (declaration)
    
    if args.input_file and args.download:
        print ("It's not possible to select an input file and to download the most "
            "recent version.")
        exit()
    if args.input_file:
        input_file = args.input_file
    elif args.download:
        print ("\nDownloading the most recent release of CC-CEDICT...")
        input_file = download_cedict()
    else:
        input_file = "cedict_ts.u8"
    if args.input_file or not (args.download or args.input_file):
        try:
            cedictfile = open(input_file, "r", encoding="utf8").read()
        except:
            print ("No CC-CEDICT file was found on this "
                "location (\"%s\").") % input_file
            quit()
    if args.download:
            cedictfile = input_file
    
    # Run conversions.
    print ("Reading and analysing the dictionary...")
    converteddict = dictconvert(cedictfile)
    print ("Converting to XDXF format...")
    xdxfdic = createxdxf(converteddict)
    # Save the resulting XDXF file.
    xdxf_result = ET.tostring(xdxfdic, encoding="utf-8", pretty_print=True,
                            xml_declaration=True,
                            doctype=doctypestring).decode("utf-8")
    xdxf_result = multi_replace(xdxf_result, [("_lb_", "<br />"), ("_lt_", "<"),
                            ("_mt_", ">")])
    if args.output_file:
        output_file = args.output_file
    else:
        output_file = "CC-CEDICT_" + dictionary_version + ".xdxf"
    open(output_file, "w", encoding="utf8").write(xdxf_result)
    print ("\nSuccess! The CC-CEDICT_ file was converted to \"%s\"." % output_file)