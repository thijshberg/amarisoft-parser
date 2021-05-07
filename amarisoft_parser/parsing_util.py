import json
import re
import math
from json import JSONDecoder
import numpy as np
import pandas as pd
import random

def tree_traverse(full_tree,target_string):
    def traverse_step(tree):
        res = []
        if isinstance(tree, dict):
            for k in tree.keys():
                if k == target_string:
                    res.append(tree[k])
                else:
                    res += traverse_step(tree[k])
        return res
    return traverse_step(full_tree)

def tree_traverse_re(full_tree,target_re):
    regex = re.compile(target_re)
    def traverse_step(tree):
        res = []
        if isinstance(tree, dict):
            for k in tree.keys():
                if regex.match(k):
                    res.append((k,tree[k]))
                else:
                    res += traverse_step(tree[k])
        return res
    return traverse_step(full_tree)

def traverse_all(data, target_string):
    res = []
    for dat in data:
        piece = tree_traverse(dat,target_string)
        if piece:
            res.append(piece)
    return res


def traverse_all_re(data, target_re):
    res = []
    for dat in data:
        piece = tree_traverse_re(dat,target_re)
        if piece:
            res.append(piece)
    return res

#For finding messages containging specific values, for example to study outliers
def find_value(dat,key,value):
    res = []
    for d in dat:
        r = tree_traverse(d,key)
        if value in ints(r):
            res.append(d)
    return res

def ints(gen):
    return [int(x) for x in gen]

def contains(s):
    def contains_(data):
        return bool(tree_traverse(data,s))
    return contains_ 

def key_is(key,value):
    def key_is_(d):
        return d[key] == value
    return key_is_


def delete_on(l,func):
    for i,x in enumerate(l):
        if func(x):
            l.pop(i)
            return l
    return l

def tget(i: int):
    def tget_(p: tuple):
        return p[i]
    return tget_
fst = tget(0)
snd = tget(1)

def find_on(l:list, func):
    for i,x in enumerate(l):
        if func(x):
            return i,x
    return -1,None

def _get(l,n,default=None):
    try:
        return l[n]
    except IndexError:
        return default

def make_unique(key, dct):
    counter = 0
    unique_key = key

    while unique_key in dct:
        counter += 1
        unique_key = '{}_{}'.format(key, counter)
    return unique_key

def parse_object_pairs(pairs):
    dct = dict()
    for key, value in pairs:
        if key in dct:
            key = make_unique(key, dct)
        dct[key] = value

    return dct

decoder = JSONDecoder(object_pairs_hook=parse_object_pairs)