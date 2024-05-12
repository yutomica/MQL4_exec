"""
【Validation】

作成日：2022/03/07
更新日：202X//

・エントリーにエッジがあるか否かの検証
・MT4にて以下の設定を行う：
　- 口座残高を9999999円に（できるだけ大きい額に設定）
　- TP、SLを設定しない
　- エキジットにはTimeStop_Exit_Forceを使用

"""

#coding : utf-8
import sys
import os
import subprocess
import shutil
from distutils.dir_util import copy_tree
from datetime import datetime
from datetime import timedelta
import datetime
import time
import pandas as pd
import numpy as np
from math import fabs
import configparser

# 入力パラメータ
EA = sys.argv[1]

# configからテスト対象を読み込む
inifile = configparser.ConfigParser()
inifile.read('./config.ini','UTF-8')
try:
    testmodel = eval(inifile.get(EA,'testmodel'))
    Terms = eval(inifile.get(EA,'Terms')) # ('M1','M5','M15','M30','H1','H4','D1')
    Symbols = eval(inifile.get(EA,'Symbols'))
    Time_STR = eval(inifile.get(EA,'Time_STR'))
    Time_END = eval(inifile.get(EA,'Time_END'))
except:
    print('Input Error !!')
    sys.exit()

# ディレクトリ設定
MT4_path = 'C:\\Users\\Yuu Tominaga\\AppData\\Roaming\\MetaQuotes\\Terminal\\A84B568DA10F82FE5A8FF6A859153D6F\\tester\\'
terminal = "\"C:\\Program Files (x86)\\Rakuten MetaTrader 4\\terminal.exe\" \""
exe_dir = 'C:\\Users\\Yuu Tominaga\\OneDrive\\MT4\\Validation\\'
if not os.path.exists(exe_dir + EA): os.mkdir(exe_dir + EA)
exe_dir = exe_dir + EA
if not os.path.exists(MT4_path+'tmpdir'): os.mkdir(MT4_path+'tmpdir')

# Trackerデータ
logfile = MT4_path+'files\\_tmp.csv'

# スクリプトにて生成するMT4入力ファイル
setfile_nm = EA+'.set'               
infile = MT4_path+'test_params.txt'
def set_inputfile(st_name,symbol,period,mode,opt_tf,date_from,date_to,outfile):
      text = "TestExpert="+st_name+"\n" \
      +"TestSymbol="+symbol+"\n" \
      +"TestPeriod="+period+"\n" \
      +"TestModel="+mode+"\n" \
      +"TestRecalculate=false\n" \
      +"TestOptimization="+opt_tf+"\n" \
      +"TestDateEnable=true\n" \
      +"TestFromDate="+date_from+"\n" \
      +"TestToDate="+date_to+"\n" \
      +"TestReport="+outfile+"\n" \
      +"TestReplaceReport=true\n" \
      +"TestShutdownTerminal=true"
      return text


print()
print(" **** Move Validation **** ")
print()
print(" EA : "+EA)
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
print("")

# バックテスト実行
cntr = 0

for trm in Terms:
      for sym in Symbols:
            excel_writer = pd.ExcelWriter(exe_dir+"\\MO_"+sym+"_"+trm+"_"+Time_STR.replace(".","")+"_"+Time_END.replace(".","")+".xlsx")
            print(' .. '+Time_STR+'-'+Time_END+' '+sym+' '+trm)
            report_path = 'tester\\tmpdir\\RESULT-'+sym+'-'+Time_END+'-'+trm+'.html'
            param = set_inputfile(EA,sym,trm,testmodel,'false',Time_STR,Time_END,report_path)
            f = open(infile,'w')
            print(param,file=f)
            f.close()
            cmd = terminal+infile+"\""
            subprocess.call(cmd)

            # ストラテジーテスト結果読み込み
            log = pd.read_csv(logfile,header=None,names=['orderno','shift','time','pl'])
            log['time'] = [datetime.datetime.fromtimestamp(x) for x in log['time']]
            
            # エントリー時刻をenに記録
            en = log.groupby(by='orderno').first()[['time']].rename(columns={'time':'OpenDateTime'})
            en['Year'] = [x.year for x in en['OpenDateTime']]
            en['hour'] = [x.hour for x in en['OpenDateTime']]
            years = list(set(en['Year']))
            hours = list(set(en['hour']))

            # 値動き算出
            # - ALL
            calctbl = log.groupby('shift').describe()['pl']
            calctbl.to_excel(excel_writer,sheet_name='ALL')
            # - 年別
            for year in years:
                orders = en[en["Year"]==year].index
                calctbl = log[log['orderno'].isin(orders)].groupby('shift').describe()['pl']
                calctbl.to_excel(excel_writer,sheet_name='Y'+str(year))
            # - 時間帯別
            for hour in hours:
                orders = en[en["hour"]==hour].index
                calctbl = log[log['orderno'].isin(orders)].groupby('shift').describe()['pl']
                calctbl.to_excel(excel_writer,sheet_name='H' + ("0"+str(hour))[-2:] )

            excel_writer.save()

#copy_tree(MT4_path+'tmpdir',exe_dir)
shutil.rmtree(MT4_path+'tmpdir')
