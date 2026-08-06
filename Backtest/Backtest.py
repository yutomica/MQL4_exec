"""
MT4バックテスト実行
 - config.iniに記載された条件にてバックテストを実行する。Terms及びSymbolsは複数条件を指定可能。
 - 実行結果はresultフォルダ下に格納される。
"""

import configparser
import shutil
import subprocess
import sys
from ast import literal_eval
from pathlib import Path, PureWindowsPath

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent / 'utils'))
from set_inputfile import set_inputfile
from STReportReader import BacktestReport

# 入力パラメータ
EA = sys.argv[1]
Time_STR = sys.argv[2]
Time_END = sys.argv[3]
EA_name, time_start_name, time_end_name = [PureWindowsPath(value).name for value in (EA, Time_STR, Time_END)]
if any(name in ('', '.', '..') for name in (EA_name, time_start_name, time_end_name)):
    raise ValueError('EA名と期間には有効な名称を指定してください')
period_name = f'{time_start_name.replace(".", "")}_{time_end_name.replace(".", "")}'

# ディレクトリ設定
setting = configparser.ConfigParser()
setting.read(BASE_DIR.parent / 'utils' / 'setting.conf')
MT4_path_windows, terminal_windows, path_output_windows = [
    PureWindowsPath(setting.get('setting', key))
    for key in ('MT4_path', 'terminal', 'path_output')
]
if any(not path.drive for path in (MT4_path_windows, terminal_windows, path_output_windows)):
    raise ValueError('setting.confにはWindowsの絶対パスを指定してください')

MT4_path, terminal, path_output = [
    Path('/mnt', path.drive.rstrip(':').lower(), *path.parts[1:])
    for path in (MT4_path_windows, terminal_windows, path_output_windows)
]
path_output /= f'BKT_{EA_name}'
tmpdir = MT4_path / 'tmpdir'

path_output.mkdir(parents=True, exist_ok=True)
tmpdir.mkdir(exist_ok=True)

# configからテスト対象を読み込む
inifile = configparser.ConfigParser()
inifile.read(BASE_DIR / 'config.ini', encoding='UTF-8')
try:
    testmodel = literal_eval(inifile.get(EA, 'testmodel'))
    Terms = literal_eval(inifile.get(EA, 'Terms'))  # ('M1','M5','M15','M30','H1','H4','D1')
    Symbols = literal_eval(inifile.get(EA, 'Symbols'))
except (configparser.Error, ValueError, SyntaxError):
    print('Input Error !!')
    sys.exit()

infile_windows = str(MT4_path_windows / 'test_params.txt')
infile = MT4_path / 'test_params.txt'

print()
print(" ** Execute Backtest ** ")
print(f" - EA : {EA}")
print()

for trm in Terms:
    for sym in Symbols:
        symbol_name, term_name = [PureWindowsPath(value).name for value in (sym, trm)]
        if any(name in ('', '.', '..') for name in (symbol_name, term_name)):
            raise ValueError('通貨ペアと時間足には有効な名称を指定してください')

        excel_path = path_output / f'Backtest_{symbol_name}_{term_name}_{period_name}.xlsx'
        report_name = f'RESULT-{symbol_name}-{time_end_name}-{term_name}.html'
        report_path_windows = str(PureWindowsPath('tester', 'tmpdir', report_name))
        param = set_inputfile(EA, sym, trm, testmodel, 'false', Time_STR, Time_END, report_path_windows)
        with infile.open('w') as f:
            print(param, file=f)

        print(subprocess.list2cmdline([str(terminal_windows), infile_windows]))
        subprocess.call([str(terminal), infile_windows])
        report = BacktestReport(tmpdir / report_name)
        with pd.ExcelWriter(excel_path) as excel_writer:
            pd.DataFrame(report.summary, index=['val']).T.to_excel(excel_writer, sheet_name='サマリ')
            report.trans.to_excel(excel_writer, sheet_name='trans')
            report.trans_y().to_excel(excel_writer, sheet_name='y')
            report.trans_ym().to_excel(excel_writer, sheet_name='ym')
            # report.trans_h().to_excel(excel_writer, sheet_name='h')
            # report.trans_wd().to_excel(excel_writer, sheet_name='wd')

shutil.copytree(tmpdir, path_output, dirs_exist_ok=True)
shutil.rmtree(tmpdir)
