import re
import datetime
from .parsing_util import tree_traverse,_get,pairwise
import numpy as np

DAY = 24*3600
DEBUG= False

lcid_pattern = re.compile("LCID:[3,4]?")
lcid_pattern1 = re.compile("LCID:[0-9][0-9]?")

def parse_mac_line(line):
    """
    Parses a line containing MAC data from the amarisoft log. It is up to the user to check whether there is a MAC line there.
    """
    splitted = line.split()
    timestamp = ''
    direction = 0
    length = 0
    try:
        timestamp = datetime.time.fromisoformat(splitted[0])
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
    data = [[diff_time(d[0],t0),*d[1:]] for d in data]
    return data

def normalize_pgw(pgw):
    if not pgw:
        return pgw
    offset = pgw[0][0]
    return [[x[0]-offset,*x[1:]] for x in pgw]

def normalize_series(series):
    if not series:
        return []
    if isinstance(series[0][0],datetime.time):
        return normalize_times(series)
    elif isinstance(series[0][0], float) or isinstance(series[0][0], np.float64):
        return normalize_pgw(series)
    else:
        raise Exception("Is this a timeseries?")

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
    """
    Checks forward through the file to find the given keyword. Bails out if there is a MAC line or the limit is reached.
    """
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

def separate_sessions_tmsi(*files,nr=False,peek_limit=120) -> dict:
    """
    This parses the given files, and gives the user data lengths for the different TMSI's.
    The result is a dict with TMSI's for keys and lists of lists of user data for each UE ID connected via this TMSI. 
    """
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
        res[id_mapping[ue_id]] += dat[ue_id]
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
    
def flatten(data):
    for key,item in data.items():
        data[key] = reduce(list.__add__,item,[])
    return data
def single_session_parser(file):
    """
    Used for parsing amarisoft log files with one phone connected. 
    It just reads all the user data lengths for all packets so if there are multiple users or sessions in the file they will all be parsed together.
    """
    res = []
    with open(file,'r') as f:
        fiter = iter(f)#we work with a specific iterator so we can go through it in functions we call
        for line in f:
            if line[0].isnumeric() and'[MAC]' in line:
                if (r := parse_mac_line(line)) is not None:
                    data,ue_id = r
                    res.append(data)
    return res


def parse_pgw(pgw):
    pgw_dat = []
    for x in pgw:
        if 'quic' in x['_source']['layers']:#QUIC is transported over UDP so do this first
            pgw_dat.append((float(tree_traverse(x,'frame.time_epoch')[0]),int(_get(tree_traverse(x,'quic.length'),0,0))))
        elif 'udp' in x['_source']['layers']:
            pgw_dat.append((float(tree_traverse(x,'frame.time_epoch')[0]),int(_get(tree_traverse(x,'data.len'),0,0))))
        elif 'tcp' in x['_source']['layers']:
            pgw_dat.append((float(tree_traverse(x,'frame.time_epoch')[0]),len(_get(tree_traverse(x,'tcp.payload'),0,[]))//3+1,_get(tree_traverse(x,'tls.app_data_proto'),0,'')))
    return [list(x[:2]) for x in pgw_dat]


def synchronize_times(series: dict):
    """
    If you have a couple of timeseries this will synchronize them, with the earliest one starting at 0.
    """
    series = {key:item for key,item in series.items() if item}
    is_epoch = {key:isinstance(s[0][0],float) for key,s in series.items() if s}
    starts = {s[0]:datetime.datetime.fromtimestamp(s[1][0][0]).time() if e[1] else s[1][0][0] for s,e in zip(series.items(),is_epoch.items())}
    debug('Starting times:',starts)
    earliest = min(starts.items(),key=lambda x: diff_time(x[1], datetime.time(0,0,0)))
    debug(earliest)
    res = {}
    for i,s in series.items():
        offset = 0
        last_time = datetime.time(0,0,0,0)
        if is_epoch[i]:
            tmp = [] 
            for x in s:
                t= datetime.datetime.fromtimestamp(x[0]).time()
                if diff_time(t, last_time) < 0:
                    offset += DAY
                last_time = t
                tmp.append([diff_time(t,earliest[1])+offset,x[-1]])
            res[i] = tmp
        else:
            tmp = []
            for x in s:
                t= x[0]
                if diff_time(t, last_time) < 0:
                    offset += DAY
                last_time = t
                tmp.append([diff_time(t,earliest[1])+offset,x[-1]])
            res[i] = tmp
    return res


def separate_times(data:dict,primary_key) -> dict:
    """
    This will, given a synchronized and homogenized dictionary of timeseries with a designated main timeseries, transform it into a dictionary timeseries with two data fields.
    These data fields corresponds to the primary timeseries data and to the smaller timeseries that ran alongside it.

    Timeseries must have the same time resolution as the lists are just zipped.


    -----------------------------------------------------------------------------------------------
    ------------------- -----------------------------------        --------------------------------

    ->

    |-----------------| |---------------------------------|        |-------------------------------|
    |-----------------| |---------------------------------|        |-------------------------------|

    """
    res = {}
    for key,item in filter(lambda x: x[0]!= primary_key and x[1], data.items()):
        start = item[0][0]
        res[key] = list(map(lambda x: x[0] + [x[1][1]],zip(item, filter(lambda y: y[0] >= start, data[primary_key]))))
    return res


def fast_activity_graph(data,resolution):
    """
    Transforms a time series into an activity graph. It's "fast" because it is faster than the first attempt.
    It uses an numpy arange which will construct the array in memory. If you call this with exorbitant bounds (e.g. mixing epoch times with absolute times) it will eat all your memory.
    """
    res = []
    active = []
    index = 0
    l = len(data)-1
    if not data:
        return []
    for i in np.arange(data[0][0],data[-1][0],resolution):
        while (x:= data[index])[0] < i +resolution:
            active.append(x)
            if index >= l:
                break
            index +=1 
        while active and active[0][0] < i -resolution:
            active.pop(0)
        res.append([i,sum(x[1] for x in active)/max(len(active),1)])
    return res

def cumulative_dict(data,primary_key,resolution=0.01):
    """
    Transforms a dictionary of timeseries into dictionary of cumulative data-througput timeseries. Cuts up the timeseries like separate_times.
    """
    def _cumulative(it):
        it_iter = iter(it)
        primary_iter = filter(lambda x: it[0][0] <= x[0] <= it[-1][0],data[primary_key])
        res = []
        total = 0
        total_primary =0
        done = False
        for i in filter(lambda _ : not done, np.arange(it[0][0],it[-1][0],resolution)):
            try:
                while (x:=next(it_iter))[0] < i:
                    total += x[1]
            except StopIteration:
                done = True
            try:
                while (x:=next(primary_iter))[0] < i:
                    total_primary += x[1]
            except StopIteration:
                done = True
            res.append([i,total,total_primary])
        return res

    return {key:_cumulative(item) for key,item in filter(lambda x: x[0] != primary_key,data.items())}