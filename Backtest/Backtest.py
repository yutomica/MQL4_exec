"""
MT4バックテスト実行
・入力パラメータ部に各種条件を指定
・最適化を実施する場合：
　Exe_OptimizeをTrueに設定
　事前にMT4ターミナルにて最適化条件を設定したsetファイルを作成し、保存しておく
　（保存先はMT4_path）
・STReportReaderとOptReportReaderをインポート

"""

#coding : utf-8
import pandas as pd
import sys
import os
import subprocess
import shutil
from distutils.dir_util import copy_tree
from datetime import datetime
from datetime import timedelta
import time
import configparser
sys.path.append('../utils')
from set_inputfile import set_inputfile
from STReportReader import BacktestReport


# 入力パラメータ
EA = sys.argv[1]

# ディレクトリ設定
setting = configparser.ConfigParser()
setting.read('../utils/setting.conf')
MT4_path = setting.get('setting','MT4_path')
terminal = setting.get('setting','terminal')
path_output = setting.get('setting','path_output')

if not os.path.exists(path_output + 'BKT_' + EA): os.mkdir(path_output + 'BKT_' + EA)
path_output = path_output + 'BKT_' + EA
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

# レポート格納ディレクトリ作成
if not os.path.exists(MT4_path+'tmpdir'):
      os.mkdir(MT4_path+'tmpdir')

infile = MT4_path+'test_params.txt'

print()
print(" ** Execute Backtest ** ")
print(" - EA : "+EA)
print()

for trm in Terms:
      for sym in Symbols:
            excel_writer = pd.ExcelWriter(path_output+"\\Backtest_"+sym+"_"+trm+"_"+Time_STR.replace(".","")+"_"+Time_END.replace(".","")+".xlsx")
            report_path = 'tester\\tmpdir\\RESULT-'+sym+'-'+Time_END+'-'+trm+'.html'
            param = set_inputfile(EA,sym,trm,testmodel,'false',Time_STR,Time_END,report_path)
            f = open(infile,'w')
            print(param,file=f)
            f.close()
            cmd = terminal+" \""+infile+"\""
            print(cmd)
            subprocess.call(cmd)
            report = BacktestReport(MT4_path[:-7]+report_path)
            pd.DataFrame(report.summary,index=['val']).T.to_excel(excel_writer,sheet_name='サマリ')
            report.trans.to_excel(excel_writer,sheet_name='trans')
            report.trans_y().to_excel(excel_writer,sheet_name='y')
            report.trans_ym().to_excel(excel_writer,sheet_name='ym')
            # report.trans_h().to_excel(excel_writer,sheet_name='h')
            # report.trans_wd().to_excel(excel_writer,sheet_name='wd')
            excel_writer.save()

copy_tree(MT4_path+'tmpdir',path_output)
shutil.rmtree(MT4_path+'tmpdir')
