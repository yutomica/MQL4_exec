"""
MT4バックテスト実行（最適化）

作成日：2017/02/10
更新日：2022/05/06

・入力パラメータ部に各種条件を指定
・事前にMT4ターミナルにて最適化条件を設定したsetファイルを作成し、保存しておく
　（保存先はMT4_path）

"""

#coding : utf-8
import sys
import os
import subprocess
import shutil
from distutils.dir_util import copy_tree
from datetime import datetime
from datetime import timedelta
import time
import pandas as pd
import numpy as np
from math import fabs
import configparser
sys.path.append('../utils')
from set_inputfile import set_inputfile_opt
from STReportReader import OptimizeReport

# 入力パラメータ
EA = sys.argv[1]

# ディレクトリ設定
setting = configparser.ConfigParser()
setting.read('../utils/setting.conf')
MT4_path = setting.get('MT4_path')
terminal = setting.get('terminal')
path_output = setting.get('path_output')

if not os.path.exists(path_output+'OPT_'+EA): os.mkdir(path_output +'OPT_'+EA)
path_output = path_output +'OPT_'+EA
if not os.path.exists(MT4_path+'tmpdir'): os.mkdir(MT4_path+'tmpdir')

# configからテスト対象を読み込む
inifile = configparser.ConfigParser()
inifile.read('./config.ini','UTF-8')
try:
    testmodel = eval(inifile.get(EA,'testmodel'))
    Terms = eval(inifile.get(EA,'Terms')) 
    Symbols = eval(inifile.get(EA,'Symbols'))
    Time_STR = eval(inifile.get(EA,'Time_STR'))
    Time_END = eval(inifile.get(EA,'Time_END'))
    TestPeriod_month = eval(inifile.get(EA,'TestPeriod_month'))
except:
    print('Input Error !!')
    sys.exit()
setfile_nm = EA+'.set' 

# テスト期間設定
TestPeriods = []
dd = datetime.strptime(Time_STR,'%Y.%m.%d')
while dd <= datetime.strptime(Time_END,'%Y.%m.%d'):
    dd_str = dd
    dd_end = dd + timedelta(30*TestPeriod_month)
    TestPeriods.append((datetime.strftime(dd_str,'%Y.%m.%d'),datetime.strftime(dd_end,'%Y.%m.%d')))
    if dd_end > datetime.strptime(Time_END,'%Y.%m.%d'):break
    dd = dd_end + timedelta(1)

# レポート格納ディレクトリ作成
if not os.path.exists(MT4_path+'tmpdir'):
    os.mkdir(MT4_path+'tmpdir')
infile = MT4_path+'test_params.txt'

print()
print(" ** Execute Optimization ** ")
print(" - EA : "+EA)
print()
print(" Parameters :")
print("  - TESTMODEL = "+testmodel)
symbols = ""
for s in Symbols: symbols += s+" "
print("  - Symbols = "+symbols)
terms = ""
for t in Terms: terms += t+" "
print("  - Periods = "+terms)
print("  - From "+Time_STR+" To "+Time_END)
for t in TestPeriods:
    print(t)
print()

# 最適化パラメータを特定
with open(MT4_path + setfile_nm) as f:
    lines = f.readlines()
opt_params = list()
for line in lines:
    if line.find("F=1")!=-1:
        opt_params.append(line.split(',')[0])

# バックテスト（最適化）
result_tbl = pd.DataFrame()
for sym in Symbols:
        for trm in Terms:
            for v in TestPeriods:
                print(' -- '+v[0]+'-'+v[1]+' '+sym+' '+trm)
                report_path = 'tester\\tmpdir\\RESULT-OPT-'+sym+'-'+v[1]+'-'+trm+'.html'
                param = set_inputfile_opt(EA,sym,trm,testmodel,'true',setfile_nm,v[0],v[1],report_path)
                f = open(infile,'w')
                print(param,file=f)
                f.close()
                cmd = terminal+" \""+infile+"\""
                subprocess.call(cmd)
                try:
                    res_summary = OptimizeReport(MT4_path[:-7]+report_path)
                    _res_tbl = res_summary.result
                    _res_tbl['TestPeriod'] = v[0]+'-'+v[1]
                    _res_tbl['Symbol'] = sym
                    _res_tbl['TimeFrame'] = trm                        
                    result_tbl = pd.concat([result_tbl,_res_tbl])
                except:
                    pass

            # 結果出力
            excel_writer = pd.ExcelWriter(path_output+"\\OPT_"+EA+"_"+sym+"_"+trm+".xlsx")
            param_columns = []
            for c in result_tbl.columns:
                if c.find('P_')!=-1: param_columns.append(c)
            result_tbl_columns = ['TestPeriod','Symbol','TimeFrame',u'パス',u'損益',u'総取引数',u'PF',u'期待利得',u'DD $',u'DD %'] + opt_params
            for param in opt_params:
                result_tbl[param] = [float(x) for x in result_tbl["P_"+param]]
                result_tbl = result_tbl.drop("P_"+param,axis=1)
            result_tbl[result_tbl_columns].to_excel(excel_writer,sheet_name='summary')
            excel_writer.save()
            
# for col in [u'損益',u'総取引数',u'PF',u'期待利得',u'DD $',u'DD %']:

#     for p in sorted(list(set(result_tbl['TestPeriod']))):
#         _result = pd.DataFrame(
#             index=sorted(list(set(result_tbl[opt_params[0]]))),
#             columns=sorted(list(set(result_tbl[opt_params[1]])))
#         )        
#         for i in sorted(list(set(result_tbl[opt_params[0]]))):
#             for c in sorted(list(set(result_tbl[opt_params[1]]))):
#                 _result.loc[i,c] = result_tbl[(result_tbl['TestPeriod']==p)&(result_tbl[opt_params[0]]==i)&(result_tbl[opt_params[1]]==c)][[col]].values[0][0]

#         _result = result_tbl[result_tbl['TestPeriod']==p][['損益']+opt_params]

# result_tbl.groupby

copy_tree(MT4_path+'tmpdir',path_output)
shutil.rmtree(MT4_path+'tmpdir')
