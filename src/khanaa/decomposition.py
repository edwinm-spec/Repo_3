import re
from typing import Any, Dict, List, Tuple, Union

from khanaa.thai_script import (CLUSTERS, CONSONANTS, DIACRITICS,
    TONE_MARKERS, VOWEL_CHAR, VOWELS)
from khanaa.word import Word
from khanaa.utils import find_tone

TONE_MARK: str = ''.join([TONE_MARKERS[tone] for tone in TONE_MARKERS])
CODA_LIST: str = ''.join([char for char in CONSONANTS
    if CONSONANTS[char]['sound_coda']
    and char not in ['ย', 'ว']])

vowel_re = None

def spelling_decompose(text: str) -> Union[Dict[str, Any], None]:
    global vowel_re
    if vowel_re is None:
        vowel_re = create_vowel_re()
    
    data = {
        'onset': '',
        'vowel': '',
        'silent_before': '',
        'coda': '',
        'silent_after': '',
        'tone': -1
    }
    
    detail = {
        'tone_mark': '',
        'leading_h': False,
        'vowel_form': '',
        'onset_index': -1,
        'onset_main': ''
    }
    
    pref = {}
    
    if not text:
        return None
    
    try:
        no_silent_after, silent_after = split_silent_after(text)
        data['silent_after'] = silent_after
        
        tone_mark = analyze_tone_mark(no_silent_after)
        detail['tone_mark'] = tone_mark
        
        vowel, extra_silent_after, matched_text, vowel_type, vowel_form = analyze_vowel(no_silent_after)
        if not vowel:
            return None
            
        data['vowel'] = vowel
        data['silent_after'] = extra_silent_after + data['silent_after']
        detail['vowel_form'] = vowel_form
        
        coda, no_coda = analyze_coda(matched_text, vowel_type)
        data['coda'] = coda
        
        no_tone = remove_tone(no_coda)
        
        silent_before = analyze_silent_before(no_tone)
        data['silent_before'] = silent_before
        if silent_before:
            no_tone = no_tone.replace(silent_before + DIACRITICS['kaaran'], '')
        
        onset, leading_h, onset_front, onset_back = analyze_onset(no_tone, vowel_form)
        data['onset'] = onset
        detail['leading_h'] = leading_h
        
        vowel_corrected, form_corrected = change_o_r(vowel, coda)
        if form_corrected:
            data['vowel'] = vowel_corrected
            detail['vowel_form'] = form_corrected
        
        if len(onset) == 1:
            detail['onset_main'] = onset
            detail['onset_index'] = -1
        else:
            if len(onset_back) > 0:
                if CONSONANTS[onset_back[-1]]['class'] == 'low_single':
                    detail['onset_index'] = -2 if len(onset) > 1 else -1
                    detail['onset_main'] = onset[detail['onset_index']]
                else:
                    detail['onset_index'] = -1
                    detail['onset_main'] = onset[-1]
            else:
                detail['onset_index'] = -1
                detail['onset_main'] = onset[-1]
        
        tone_num = find_tone(detail['onset_main'], data['vowel'], data['coda'], tone_mark, detail['leading_h'])
        data['tone'] = tone_num
        
        if onset_front and onset_back:
            pref.update(find_onset_pref(onset_front, onset_back, tone_mark))
        
        if data['silent_after']:
            pref['silent_after_style'] = 'plain'
        
        if data['onset'] and len(data['onset']) > 1:
            if data['onset'] not in CLUSTERS:
                pref['clear_vowel'] = False
                pref['clear_vowel_onset'] = 'not_true_cluster'
                pref['clear_vowel_tone_mark'] = False
        
        return {
            'data': data,
            'detail': detail,
            'pref': pref
        }
    
    except Exception:
        return None

def replace_vowel_re(form: str) -> str:
    form: str = form.replace('+', f'[{TONE_MARK}]?')
    form = form.replace('-', '[ก-ฮ]+')
    form = ''.join(['^[ก-ฮ]*', form])
    return form

def create_vowel_re():
    vowel_re = {'vowel_jw': {}, 'vowel_coda': {}, 'vowel_no_coda': {}}
    for vowel in VOWELS:
        if (VOWELS[vowel]['form_no_coda']
                and VOWELS[vowel]['sound_coda'] in ['j', 'w']):
            vowel_re['vowel_jw'].update({vowel: VOWELS[vowel]['form_no_coda']})
        if VOWELS[vowel]['form_with_coda']:
            vowel_re['vowel_coda'].update({vowel: VOWELS[vowel]['form_with_coda']})
        if (VOWELS[vowel]['form_no_coda']
                and VOWELS[vowel]['sound_coda'] not in ['j', 'w']):
            vowel_re['vowel_no_coda'].update({vowel: VOWELS[vowel]['form_no_coda']})
    
    vowel_re['vowel_coda'].pop('อ')
    vowel_re['vowel_coda'].pop('โอะ')
    vowel_re['vowel_no_coda'].pop('อ')
    vowel_re.update({'ex_coda': {'โอะ': VOWELS['โอะ']['form_with_coda']}})
    vowel_re.update({'ex_no_coda': {'อ': VOWELS['อ']['form_no_coda']}})

    for vowel_type, vowel_data in vowel_re.items():
        sorted_vowel = sorted(vowel_re[vowel_type],
            key=lambda vowel: len(vowel_re[vowel_type][vowel]), reverse=True)
        additional = ''
        if vowel_type == 'vowel_jw':
            additional = f'(?![์{TONE_MARK}])'
        elif vowel_type in ['vowel_coda', 'ex_coda']:
            additional = f'([ก-ฮ]+์)?[{CODA_LIST}](?![์{TONE_MARK}])'
        new_vowel_data = {}
        for vowel in sorted_vowel:
            pattern = re.compile(
                replace_vowel_re(vowel_data[vowel]) + additional)
            new_vowel_data.update({
                vowel: {
                    'form': vowel_data[vowel],
                    're': pattern}})
        vowel_re[vowel_type] = new_vowel_data
    return vowel_re

def split_silent_after(text: str) -> Tuple[str, str]:
    no_silent_after: str = text
    silent_after: str = ''
    if text[-1] == DIACRITICS['kaaran']:
        result: List[str] = re.split(f'([ก-ฮ][{VOWEL_CHAR}]?์$)', text)
        if len(result) > 1:
            no_silent_after = result[0]
            silent_after = result[1].replace('์', '')
    return no_silent_after, silent_after

def analyze_tone_mark(text: str):
    tone_mark = ''
    for char in TONE_MARK:
        if char in text:
            tone_mark = char
            break
    for name, tone_char in TONE_MARKERS.items():
        if tone_mark == tone_char:
            tone_mark = name
            break
    return tone_mark

def analyze_vowel(text: str) -> Tuple[str, str, str, str, str]:
    all_vowels: List[str] = [char for char in text if char in VOWEL_CHAR]
    vowel, silent_after, no_silent_after, vowel_form = '', '', '', ''
    for vowel_type in vowel_re:
        result = analyze_vowel_form(text, all_vowels, vowel_type)
        if result[0]:
            vowel, silent_after, no_silent_after, vowel_form = result
            break
    return vowel, silent_after, no_silent_after, vowel_type, vowel_form

def analyze_vowel_form(text: str, all_vowels: List[str],
        vowel_type: str) -> Tuple[str, str, str, str]:
    for vowel in vowel_re[vowel_type]:
        form = vowel_re[vowel_type][vowel]['form']
        pattern = vowel_re[vowel_type][vowel]['re']
        result = re.search(pattern, text)
        if result:
            leftover = [char for char in all_vowels if char not in form]
            if leftover:
                if (len(leftover) == 1
                        and leftover[0] in ['ิ', 'ุ']
                        and text[-1] in ['ิ', 'ุ']):
                    continue
                else:
                    continue
            split = re.split(pattern, text)
            silent_after = ''
            if split[-1]:
                if (vowel_type == 'vowel_jw'
                        and split[-1].find(DIACRITICS['kaaran']) == -1):
                    continue
                silent_after = split[-1].replace(DIACRITICS['kaaran'], '')
            return vowel, silent_after, result[0], form
    return '', '', '', ''

def analyze_coda(text: str, vowel_type: str) -> Tuple[str, str]:
    coda = ''
    if vowel_type not in ['vowel_coda', 'ex_coda']:
        coda = text[-1]
        text = text[:-1]
    return coda, text

def remove_tone(text: str) -> str:
    for char in TONE_MARK:
        text = text.replace(char, '')
    return text

def analyze_onset(matched_text: str, vowel_form: str) -> Tuple[
        str, bool, str, str]:
    vowel_form = vowel_form.replace('+', '')
    char_before, char_after = vowel_form.split('-')
    pattern = f'(?<={char_before})[ก-ฮ]+(?={char_after})'
    onset_back = re.search(re.compile(pattern), matched_text)[0]
    onset_back, leading_h = analyze_leading_h(onset_back)

    onset_front = ''
    if char_before:
        pattern_front = f'[ก-ฮ]+(?={char_before})'
        found_onset = re.search(re.compile(pattern_front), matched_text)
        if found_onset:
            onset_front = found_onset[0]
    onset = ''.join([onset_front, onset_back])
    return onset, leading_h, onset_front, onset_back

def analyze_leading_h(onset: str) -> Tuple[str, bool]:
    leading_h: bool = False
    if ('ห' in onset
            and len(onset) > onset.index('ห')+1
            and CONSONANTS[onset[onset.index('ห')+1]]['class']
                == 'low_single'):
        leading_h = True
        onset = onset.replace('ห', '')
    return onset, leading_h

def find_onset_pref(onset_front: str, onset_back: str,
        tone_mark: str) -> Dict[str, bool]:
    clear_vowel = True
    clear_vowel_onset = 'not_true_cluster'
    clear_vowel_tone_mark = False
    if tone_mark:
        if len(onset_back) == 2:
            clear_vowel_tone_mark = False
        elif len(onset_front) == 1:
            clear_vowel_tone_mark = True
    if onset_front + onset_back in CLUSTERS:
        if len(onset_back) == 2:
            clear_vowel_onset = 'not_true_cluster'
        elif len(onset_front) == 1:
            clear_vowel_onset = 'all'
    else:
        if len(onset_back) == 2:
            clear_vowel = False
        elif len(onset_front) == 1:
            clear_vowel = True
    return {'clear_vowel': clear_vowel,
        'clear_vowel_onset': clear_vowel_onset,
        'clear_vowel_tone_mark': clear_vowel_tone_mark}

def analyze_silent_before(text: str) -> str:
    silent_before: str = ''
    if text[-1] == DIACRITICS['kaaran']:
        silent_before = text[-2]
    return silent_before

def change_o_r(vowel: str, coda: str) -> Tuple[str, str]:
    form: str = ''
    if vowel == 'โอะ' and coda == 'ร':
        vowel = 'ออ'
        form = '-+'
    return vowel, form

def save_h_thoo(tone: int, h_present: bool) -> bool:
    low_single_h_thoo: bool = False
    if tone == 2 and h_present:
        low_single_h_thoo = True
    return low_single_h_thoo