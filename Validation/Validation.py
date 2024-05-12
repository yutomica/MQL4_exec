"""
【Validation】

作成日：2022/03/02
更新日：2022/05/05

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
sys.path.append('../utils')
from set_inputfile import set_inputfile

# 入力パラメータ
EA = sys.argv[1]

# ディレクトリ設定
setting = configparser.ConfigParser()
setting.read('../utils/setting.conf')
MT4_path = setting.get('Validation','MT4_path')
terminal = setting.get('Validation','terminal')
exe_dir = setting.get('Validation','exe_dir')

if not os.path.exists(exe_dir + EA): os.mkdir(exe_dir + EA)
exe_dir = exe_dir + EA
if not os.path.exists(MT4_path+'tmpdir'): os.mkdir(MT4_path+'tmpdir')

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



# Trackerデータ
logfile = MT4_path+'files\\_tmp.csv'

# スクリプトにて生成するMT4入力ファイル
setfile_nm = EA+'.set'               
infile = MT4_path+'test_params.txt'

print()
print(" **** Validation **** ")
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
            excel_writer_EV = pd.ExcelWriter(exe_dir+"\\EV_"+sym+"_"+trm+"_"+Time_STR.replace(".","")+"_"+Time_END.replace(".","")+".xlsx")
            excel_writer_MV = pd.ExcelWriter(exe_dir+"\\MV_"+sym+"_"+trm+"_"+Time_STR.replace(".","")+"_"+Time_END.replace(".","")+".xlsx")
            
            print(' .. '+Time_STR+'-'+Time_END+' '+sym+' '+trm)
            report_path = 'tester\\tmpdir\\RESULT-'+sym+'-'+Time_END+'-'+trm+'.html'
            param = set_inputfile(EA,sym,trm,testmodel,'false',Time_STR,Time_END,report_path)
            f = open(infile,'w')
            print(param,file=f)
            f.close()
            cmd = terminal+" \""+infile+"\""
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
            maxshift = int(log['shift'].max())
            minshift = int(log['shift'].min())

            # ### Edge Validation ###
            # MAE/MFE算出
            calctbl = pd.DataFrame()
            for t in range(minshift,maxshift+1):
                  calc_orders = list(set(log[log['shift'] == t]['orderno']))
                  _log = log[(log['shift'] <= t)&(log['orderno'].isin(calc_orders))]
                  _log_plmax = _log.groupby(by=['orderno']).max()[['pl']].rename(columns={'pl':'MFE'})
                  _log_plmin = _log.groupby(by=['orderno']).min()[['pl']].rename(columns={'pl':'MAE'})
                  _log = en.join(_log_plmax).join(_log_plmin)
                  _log['shift'] = t
                  calctbl = pd.concat([calctbl,_log])

            # 集計
            # EdgeRatio 年＆時間別
            tbl_year_hour = calctbl[calctbl['shift']==minshift].groupby(['Year','hour']).size().to_frame(name='n_orders')
            _tbl = pd.DataFrame(index=tbl_year_hour.index,columns=[str(x) for x in range(minshift,maxshift+1)])
            tbl_year_hour = pd.merge(tbl_year_hour,_tbl,left_index=True,right_index=True)
            calc = calctbl.groupby(['Year','hour','shift']).mean()[['MFE','MAE']]
            calc.loc[:,"E"] = [np.nan if y==0 else fabs(x/y) for x,y in zip(calc["MFE"],calc["MAE"])]
            for y in sorted(list(set(en['Year']))):
                for h in sorted(list(set(en['hour']))):
                    try:
                        tbl_year_hour.loc[(y,h),[str(x) for x in range(minshift,maxshift+1)]] = calc.loc[(y,h),"E"].values
                    except: pass
            tbl_year_hour.to_excel(excel_writer_EV,sheet_name='ER_Year_hour')

            # EdgeRatio 年別
            tbl_year = calctbl[calctbl['shift']==minshift].groupby(['Year']).size().to_frame(name='n_orders')
            _tbl = pd.DataFrame(index=tbl_year.index,columns=[str(x) for x in range(minshift,maxshift+1)])
            tbl_year = pd.merge(tbl_year,_tbl,left_index=True,right_index=True)
            calc = calctbl.groupby(['Year','shift']).mean()[['MFE','MAE']]
            calc.loc[:,"E"] = [np.nan if y==0 else fabs(x/y) for x,y in zip(calc["MFE"],calc["MAE"])]
            for y in sorted(list(set(en['Year']))):
                try:
                    tbl_year.loc[y,[str(x) for x in range(minshift,maxshift+1)]] = calc.loc[y,"E"].values
                except: pass
            tbl_year.to_excel(excel_writer_EV,sheet_name='ER_Year')

            # EdgeRatio 時間別
            tbl_hour = calctbl[calctbl['shift']==minshift].groupby(['hour']).size().to_frame(name='n_orders')
            _tbl = pd.DataFrame(index=tbl_hour.index,columns=[str(x) for x in range(minshift,maxshift+1)])
            tbl_hour = pd.merge(tbl_hour,_tbl,left_index=True,right_index=True)
            calc = calctbl.groupby(['hour','shift']).mean()[['MFE','MAE']]
            calc.loc[:,"E"] = [np.nan if y==0 else fabs(x/y) for x,y in zip(calc["MFE"],calc["MAE"])]
            for y in sorted(list(set(en['hour']))):
                try:
                    tbl_hour.loc[y,[str(x) for x in range(minshift,maxshift+1)]] = calc.loc[y,"E"].values
                except: pass
            tbl_hour.to_excel(excel_writer_EV,sheet_name='ER_hour')

            # ### Move Validation ###
            # - ALL
            calctbl = log.groupby('shift').describe()['pl']
            calctbl.to_excel(excel_writer_MV,sheet_name='ALL')
            # - 年別
            for year in years:
                orders = en[en["Year"]==year].index
                calctbl = log[log['orderno'].isin(orders)].groupby('shift').describe()['pl']
                calctbl.to_excel(excel_writer_MV,sheet_name='Y'+str(year))
            # - 時間帯別
            for hour in hours:
                orders = en[en["hour"]==hour].index
                calctbl = log[log['orderno'].isin(orders)].groupby('shift').describe()['pl']
                calctbl.to_excel(excel_writer_MV,sheet_name='H' + ("0"+str(hour))[-2:] )

            excel_writer_EV.save()
            excel_writer_MV.save()

#copy_tree(MT4_path+'tmpdir',exe_dir)
shutil.rmtree(MT4_path+'tmpdir')
