import re
import datetime

DAY = 24*3600
DEBUG= False
def parse_amari_log(filename):
    res = []
    with open(filename,'r') as f:
        for line in f:
            if line[0]=='#':
                continue
            elif line[0].isnumeric() and'[MAC]' in line:
                if (data,_ := parse_mac_line(line)) is not None:
                    res.append(data)
    return res

lcid_pattern = re.compile("LCID:[0-9][0-9]?")
def parse_mac_line(line):
    splitted = line.split()
    timestamp = ''
    direction = 0
    length = 0
    try:
        timestamp = datetime.time.fromisoformat(splitted[0])
        #if not (a[3] in CELL_ID and a[4] in UE_ID):
        #    return None
        if not (direction:= splitted[2]) in ['UL','DL']:
            return None
        for a,b in pairwise(splitted[5:]):
            if lcid_pattern.match(a):
                length += int(b[4:])
    except IndexError:
        return None
    if length:
        try:
            return [timestamp,length],int(splitted[3],16)#UE_ID
        except IndexError as e:
            debug('index error in',splitted)


def diff_time(a:datetime.time,b:datetime.time):
    """
    a-b in seconds
    """
    return 3600 * (a.hour -b.hour) + 60*(a.minute-b.minute) + (a.second-b.second) + (a.microsecond-b.microsecond)/1000000

def normalize_times(data):
    t0 = data[0][0]
    data = [[diff_time(d[0],t0),d[1:]] for d in data]
    return data


def debug(*args):
    if DEBUG:
        print("[DEBUG]",*args)

class PeekException(Exception):
    pass

class PeekRunOutException(PeekException):
    pass

class PeekMACException(PeekException):
    def __init__(self,line,lines_done):
        self.line =line
        self.lines_done = lines_done

def base16caster(s):
    """
    The amarisoft logs sometimes contain a different format hex number
    """
    if s[-1] =='H':
        chopped = f"0x{s[:-1]}".replace("'","",2)
    else:
        chopped = s
    try:
        return int(chopped,16)
    except Exception:
        raise CastError(chopped)

def peeker(keyword,caster=int,limit=15):
    def line_peeker(lines):
        for l,i in zip(lines,range(limit)):
            if 'MAC' in l:
                raise PeekMACException(l,i)
            if keyword in l:
                try:
                    return caster(l.split()[-1])
                except:
                    continue
        raise PeekRunOutException(f"Did not find {keyword}!")
    return line_peeker
ue_id_peeker = peeker('eNB-UE-S1AP-ID')
tmsi_peeker = peeker('m-TMSI',caster=base16caster)
tmsi_peeker_long = peeker('M-TMSI',caster=base16caster)

class CastError(Exception):
    pass

def separate_sessions_tmsi(*files,nr=False,peek_limit=120):
    res = {}
    id_mapping = {}
    dat = {}
    if nr:
        tmsi_peeker = peeker('5G-TMSI',caster=base16caster,limit=100)
    else:
        tmsi_peeker = peeker('m-TMSI',caster=base16caster)
    def start_session(ue_id,fiter):
        debug(f'finding Id {ue_id}')
        while True:
            try:
                tmsi = tmsi_peeker(fiter)
                break
            except PeekRunOutException as e:
                limit = peek_limit
                while limit:
                    try:
                        tmsi = peeker('M-TMSI',caster=base16caster,limit=limit)(fiter)
                    except PeekRunOutException as e:
                        debug("ran out!")
                        break
                    except PeekMACException as e:
                        mac_line(e.line)
                        limit -= e.lines_done
                debug('did not find TMSI')
                return
            except PeekMACException as e:
                mac_line(e.line)
        if tmsi not in res:
            res[tmsi] = []
            debug('found tmsi',tmsi)
        id_mapping[int(ue_id,16)] = tmsi
        dat[int(ue_id,16)] = []
        debug("registering",int(ue_id,16),tmsi)
    def finish_session(ue_id,pop=True):
        res[id_mapping[ue_id]].append(dat[ue_id])
        if pop:
            dat.pop(ue_id)
            id_mapping.pop(ue_id)
        debug('release',ue_id)
    def mac_line(line):
        if (r := parse_mac_line(line)) is not None:
            data,ue_id = r
            if not ue_id in id_mapping:
                return
            dat[ue_id].append(data)
    for file in files:
        with open(file,'r') as f:
            fiter = iter(f)#we work with a specific iterator so we can go through it in functions we call
            for line in fiter:
                if line[0]=='#':
                    continue
                elif 'RRC Connection Request' in line:
                    ue_id = line.split()[3]
                    if int(ue_id,16) == -1:
                        return res
                    start_session(ue_id,fiter)
                elif nr and '5GMM: Service request' in line:
                    ue_id = line.split()[3]
                    start_session(ue_id,fiter)
                elif 'UE context release command' in line:
                    ue_id = ue_id_peeker(fiter)
                    if ue_id in id_mapping:
                        finish_session(ue_id)
                elif line[0].isnumeric() and '[MAC]' in line:
                    mac_line(line)
    if dat:
        ue_iter = iter(dat)
        for ue_id in ue_iter:
            finish_session(ue_id,pop=False)
            debug("final release", ue_id)
    return res

def single_session_parser(file):
    res = []
    with open(file,'r') as f:
        fiter = iter(f)#we work with a specific iterator so we can go through it in functions we call
        for line in f:
            if line[0].isnumeric() and'[MAC]' in line:
                if (r := parse_mac_line(line)) is not None:
                    data,ue_id = r
                    res.append(data)
    return res