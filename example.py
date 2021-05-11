#%%
from amarisoft_parser.parse import *
from amarisoft_parser.parsing_util import flatten
import json
import matplotlib.pyplot as plt
from itertools import repeat

def plot_timeseries(series,form='b',labels = None):
    if not series or not series[0]:
        return
    no_labels =False
    if (no_labels := not labels):
        labels = repeat(None)
    n = len(series[0])
    for i,label in zip(range(1,n),labels):
        plt.plot([x[0] for x in series],[x[i] for x in series],form, alpha = 1/(n-1),label=label)
    if not no_labels:
        plt.legend()
    plt.show()

#%%

with open('4G-oneplus_single-tun0_ap-False_shuffle-False-20reps_run_0.pcap.json','r') as f:
    pgw = parse_pgw(json.load(f))

enb = single_session_parser('enb0_4g-single-oneplus.log')#This is done with opening the file in the function as the log can be cut up into separate files, in which case you can provide multiple filenames and parse them together.

separated = separate_sessions_tmsi('run5_lte.log',nr=False,peek_limit=3000)

#%%

plot_timeseries(normalize_series(pgw),'b.')
print('-'*50)
plot_timeseries(normalize_series(enb),'b.')
print('-'*50)

for key,item in separated.items():
    print(key)
    plot_timeseries(normalize_series(item),'g.')