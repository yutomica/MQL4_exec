
# 処理名：ストラテジーテスターレポートの読み込み
# encoding = utf-8

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from math import fabs
    
def num_chk(indata):
    try:
        if indata.replace(".","").replace(",","").replace("-","").isdigit():return indata
        else:return "0"
    except:
        return "0"

def timedelta_to_DHM(td):
    sec = td.total_seconds()
    return str(int(sec//86400))+'D/'+str(int(sec%86400//3600))+'H/'+str(int(sec%86400%3600//60))+'M'

# バックテストレポート読み込み（最適化なし）
class BacktestReport:
    def __init__(self,filepath):
        source = open(filepath,'r')
        soup = BeautifulSoup(source,features="html.parser")
        # サマリテーブル読み込み
        sline = soup.findAll("table")[0].findAll("tr")
        self.summary = dict()
        self.summary['Symbol'] = sline[0].findAll("td")[1].string
        self.summary[u'期間'] = sline[1].findAll("td")[1].string
        self.summary['Period'] = self.summary[u'期間'][self.summary[u'期間'].find('(')+1:self.summary[u'期間'].find(')')]
        self.summary['Time_Start'] = self.summary[u'期間'][self.summary[u'期間'].find(')')+3:self.summary[u'期間'].find('-')-1]
        self.summary['Time_End'] = self.summary[u'期間'][self.summary[u'期間'].find('-')+2:self.summary[u'期間'].find('-')+2+16]
        self.summary[u'モデル'] = sline[2].findAll("td")[1].string
        self.summary[u'パラメーター'] = sline[3].findAll("td")[1].string
        self.summary[u'テストバー数'] = int(num_chk(sline[5].findAll("td")[1].string))
        self.summary[u'不整合チャートエラー'] = int(num_chk(sline[6].findAll("td")[1].string))
        self.summary[u'初期証拠金'] = float(num_chk(sline[8].findAll("td")[1].string))
        self.summary[u'モデルティック数'] = int(num_chk(sline[5].findAll("td")[3].string))
        self.summary[u'モデリング品質'] = sline[5].findAll("td")[5].string
        self.summary['Spread'] = sline[8].findAll("td")[5].string
        self.summary[u'総取引数'] = int(num_chk(sline[13].findAll("td")[1].string))
        self.summary[u'取引数（売）'] = int(num_chk(sline[13].findAll("td")[3].string[:sline[13].findAll("td")[3].string.find("(")]))
        self.summary[u'取引数（買）'] = int(num_chk(sline[13].findAll("td")[5].string[:sline[13].findAll("td")[5].string.find("(")]))
        self.summary[u'純益'] = float(num_chk(sline[9].findAll("td")[1].string))
        self.summary[u'総利益'] = float(num_chk(sline[9].findAll("td")[3].string))
        self.summary[u'総損失'] = float(num_chk(sline[9].findAll("td")[5].string))
        self.summary[u'期待利得'] = float(num_chk(sline[10].findAll("td")[3].string))
        self.summary[u'プロフィットファクタ'] = float(num_chk(sline[10].findAll("td")[1].string))
        self.summary[u'最大ドローダウン（金額）'] = float(num_chk(sline[11].findAll("td")[3].string[:sline[11].findAll("td")[3].string.find("(")]))
        self.summary[u'最大ドローダウン（%）'] = float(num_chk(sline[11].findAll("td")[3].string[sline[11].findAll("td")[3].string.find("(")+1:sline[11].findAll("td")[3].string.find(")")].replace("%","")))/100
        self.summary[u'絶対ドローダウン'] = float(num_chk(sline[11].findAll("td")[1].string))
        #self.summary[u'相対ドローダウン'] = sline[11].findAll("td")[5].string
        self.summary[u'勝率'] = float(num_chk(sline[14].findAll("td")[2].string[sline[14].findAll("td")[2].string.find("(")+1:sline[14].findAll("td")[2].string.find(")")].replace("%","")))/100
        self.summary[u'勝率（売）'] = float(num_chk(sline[13].findAll("td")[3].string[sline[13].findAll("td")[3].string.find("(")+1:sline[13].findAll("td")[3].string.find(")")].replace("%","")))/100
        self.summary[u'勝率（買）'] = float(num_chk(sline[13].findAll("td")[5].string[sline[13].findAll("td")[5].string.find("(")+1:sline[13].findAll("td")[5].string.find(")")].replace("%","")))/100
        self.summary[u'勝トレード数'] = int(num_chk(sline[14].findAll("td")[2].string[:sline[14].findAll("td")[2].string.find("(")-1]))
        self.summary[u'負トレード数'] = int(num_chk(sline[14].findAll("td")[4].string[:sline[14].findAll("td")[4].string.find("(")-1]))
        self.summary[u'最大利益'] = float(num_chk(sline[15].findAll("td")[2].string))
        self.summary[u'最大損失'] = float(num_chk(sline[15].findAll("td")[4].string))
        self.summary[u'平均利益'] = float(num_chk(sline[16].findAll("td")[2].string))
        self.summary[u'平均損失'] = float(num_chk(sline[16].findAll("td")[4].string))
        self.summary[u'最大連勝数'] = int(num_chk(sline[17].findAll("td")[2].string[:sline[17].findAll("td")[2].string.find("(")-1]))
        self.summary[u'最大連勝額'] = float(num_chk(sline[17].findAll("td")[2].string[sline[17].findAll("td")[2].string.find("(")+1:sline[17].findAll("td")[2].string.find(")")]))
        self.summary[u'最大連敗数'] = int(num_chk(sline[17].findAll("td")[4].string[:sline[17].findAll("td")[4].string.find("(")-1]))
        self.summary[u'最大連敗額'] = float(num_chk(sline[17].findAll("td")[4].string[sline[17].findAll("td")[4].string.find("(")+1:sline[17].findAll("td")[4].string.find(")")]))
        self.summary[u'平均連勝数'] = int(num_chk(sline[19].findAll("td")[2].string))
        self.summary[u'平均連敗数'] = int(num_chk(sline[19].findAll("td")[4].string))
        # 明細テーブル読み込み
        tline = soup.findAll('table')[1].findAll('tr')
        lst_no = [] #No.
        lst_time = [] #時間
        lst_type = [] #取引種別
        lst_order = [] #注文番号
        lst_vol = [] #数量
        lst_price = [] #価格
        lst_sl = [] #決済逆指値(S/L)
        lst_tp = [] #決済指値(T/P)
        lst_prof = [] #損益
        lst_zan = [] #残高
        for ln in tline[1:]:
            lst_no.append(ln.findAll("td")[0].string)
            lst_time.append(datetime.strptime(ln.findAll("td")[1].string,'%Y.%m.%d %H:%M'))
            lst_type.append(ln.findAll("td")[2].string)
            lst_order.append(int(ln.findAll("td")[3].string))
            lst_vol.append(float(ln.findAll("td")[4].string))
            lst_price.append(float(ln.findAll("td")[5].string))
            lst_sl.append(float(ln.findAll("td")[6].string))
            lst_tp.append(float(ln.findAll("td")[7].string))
            if len(ln.findAll("td")) > 9:
                lst_prof.append(float(ln.findAll("td")[8].string))
                lst_zan.append(float(ln.findAll("td")[9].string))
            else:
                lst_prof.append(np.nan)
                lst_zan.append(np.nan)
        df = pd.DataFrame({
            u'時間' : lst_time,
            u'取引種別' : lst_type,
            #u'注文番号' : lst_order,
            u'数量' : lst_vol,
            u'価格' : lst_price,
            u'決済逆指値(S/L)' : lst_sl,
            u'決済指値(T/P)' : lst_tp,
            u'損益' : lst_prof,
            u'残高' : lst_zan
        },index=lst_order)
        _open = df.groupby(level=0).first()[[u'取引種別',u'数量',u'時間',u'価格',u'決済逆指値(S/L)',u'決済指値(T/P)']]
        _open = _open.rename(columns={u'取引種別':u'約定種別',u'時間':u'約定日時',u'価格':u'約定価格'})
        _close = df.groupby(level=0).last()[[u'取引種別',u'時間',u'価格',u'損益',u'残高']]
        _close = _close.rename(columns={u'取引種別':u'決済種別',u'時間':u'決済日時',u'価格':u'決済価格'})
        _modify = df_modify = df[df[u'取引種別'] == 'modify'][[u'取引種別']].groupby(level=0).count().rename(columns={u'取引種別':u'変更回数'})
        self.trans = _open.merge(_close,how='inner',left_index=True,right_index=True)
        self.trans = self.trans.merge(_modify,how='left',left_index=True,right_index=True).fillna(0)
        self.trans['約定'] = [1 if x!='delete' else 0 for x in self.trans['決済種別']]
        self.trans['損益(pips)'] = self.trans['損益']/(1000*self.trans['数量'])
        self.trans['Risk'] = [fabs(x-y) for x,y in zip(self.trans['約定価格'],self.trans['決済逆指値(S/L)'])]
        self.trans['Profit'] = [x-y if z=='buy' else y-x for x,y,z in zip(self.trans['決済価格'],self.trans['約定価格'],self.trans['約定種別'])]
        self.trans['R'] = [x/y if y!=0 else np.nan for x,y in zip(self.trans['Profit'],self.trans['Risk'])]
        self.trans['勝敗'] = [1 if x>0 else 0 for x in self.trans['損益']]
        self.trans['勝敗'] = [np.nan if x==0. else y for x,y in zip(self.trans['損益'],self.trans['勝敗'])]
        self.trans['保有期間'] = self.trans['決済日時'] - self.trans['約定日時']
        self.trans['残高'] = [np.nan if x=='delete' else y for x,y in zip(self.trans['決済種別'],self.trans['残高'])]
        self.trans['残高'] = self.trans['残高'].fillna(method='ffill')
        self.trans['YYYYMM'] = list([datetime.strftime(x,"%Y-%m") for x in self.trans['決済日時']])
        self.trans['YYYY'] = list([datetime.strftime(x,"%Y") for x in self.trans['決済日時']])
        self.trans['H'] = list([datetime.strftime(x,"%H") for x in self.trans['約定日時']])
        yobi = ["1:月","2:火","3:水","4:木","5:金","6:土","7:日"]
        self.trans['WD'] = list([yobi[x.weekday()] for x in self.trans['約定日時']])
    # 年次サマリ
    def trans_y(self):
        trans_y = self.trans.groupby('YYYY').count()[['決済種別']].rename(columns={'決済種別':'取引回数'})
        trans_y = trans_y.join(self.trans.groupby('YYYY').sum()[['約定']].rename(columns={'約定':'約定回数'}))
        trans_y = trans_y.join(self.trans[self.trans['勝敗']==1].groupby('YYYY').count()[['約定']].rename(columns={'約定':'勝トレード数'}))
        trans_y = trans_y.join(self.trans[self.trans['勝敗']==0].groupby('YYYY').count()[['約定']].rename(columns={'約定':'負トレード数'}))
        trans_y = trans_y.join(self.trans.groupby('YYYY').mean()[['勝敗']].rename(columns={'勝敗':'勝率'}))
        trans_y = trans_y.join(self.trans.groupby('YYYY').sum()[['損益(pips)']])
        trans_y = trans_y.join(self.trans[self.trans['勝敗']==1].groupby('YYYY').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均利益(pips/trade)'}))
        trans_y = trans_y.join(self.trans[self.trans['勝敗']==0].groupby('YYYY').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均損失(pips/trade)'}))
        trans_y = trans_y.join(self.trans.groupby('YYYY').max()[['保有期間']].rename(columns={'保有期間':'最大保有期間(h)'}))
        trans_y = trans_y.join(self.trans.groupby('YYYY').min()[['保有期間']].rename(columns={'保有期間':'最小保有期間(h)'}))
        trans_y = trans_y.fillna({'勝トレード数':0,'負トレード数':0,'平均利益(pips/trade)':0,'平均損失(pips/trade)':0})
        trans_y['勝トレード数'] = [int(x) for x in trans_y['勝トレード数']]
        trans_y['負トレード数'] = [int(x) for x in trans_y['負トレード数']]
        trans_y['最大保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_y['最大保有期間(h)']]
        trans_y['最小保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_y['最小保有期間(h)']]
        return trans_y
    # 月次サマリ
    def trans_ym(self):
        trans_ym = self.trans.groupby('YYYYMM').count()[['決済種別']].rename(columns={'決済種別':'取引回数'})
        trans_ym = trans_ym.join(self.trans.groupby('YYYYMM').sum()[['約定']].rename(columns={'約定':'約定回数'}))
        trans_ym = trans_ym.join(self.trans[self.trans['勝敗']==1].groupby('YYYYMM').count()[['約定']].rename(columns={'約定':'勝トレード数'}))
        trans_ym = trans_ym.join(self.trans[self.trans['勝敗']==0].groupby('YYYYMM').count()[['約定']].rename(columns={'約定':'負トレード数'}))
        trans_ym = trans_ym.join(self.trans.groupby('YYYYMM').mean()[['勝敗']].rename(columns={'勝敗':'勝率'}))
        trans_ym = trans_ym.join(self.trans.groupby('YYYYMM').sum()[['損益(pips)']])
        trans_ym = trans_ym.join(self.trans[self.trans['勝敗']==1].groupby('YYYYMM').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均利益(pips/trade)'}))
        trans_ym = trans_ym.join(self.trans[self.trans['勝敗']==0].groupby('YYYYMM').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均損失(pips/trade)'}))
        trans_ym = trans_ym.join(self.trans.groupby('YYYYMM').max()[['保有期間']].rename(columns={'保有期間':'最大保有期間(h)'}))
        trans_ym = trans_ym.join(self.trans.groupby('YYYYMM').min()[['保有期間']].rename(columns={'保有期間':'最小保有期間(h)'}))
        trans_ym = trans_ym.fillna({'勝トレード数':0,'負トレード数':0,'平均利益(pips/trade)':0,'平均損失(pips/trade)':0})
        trans_ym['勝トレード数'] = [int(x) for x in trans_ym['勝トレード数']]
        trans_ym['負トレード数'] = [int(x) for x in trans_ym['負トレード数']]
        trans_ym['最大保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_ym['最大保有期間(h)']]
        trans_ym['最小保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_ym['最小保有期間(h)']]
        return trans_ym
    # En時間帯別サマリ
    def trans_h(self):
        trans_h = self.trans.groupby('H').count()[['決済種別']].rename(columns={'決済種別':'取引回数'})
        trans_h = trans_h.join(self.trans.groupby('H').sum()[['約定']].rename(columns={'約定':'約定回数'}))
        trans_h = trans_h.join(self.trans[self.trans['勝敗']==1].groupby('H').count()[['約定']].rename(columns={'約定':'勝トレード数'}))
        trans_h = trans_h.join(self.trans[self.trans['勝敗']==0].groupby('H').count()[['約定']].rename(columns={'約定':'負トレード数'}))
        trans_h = trans_h.join(self.trans.groupby('H').mean()[['勝敗']].rename(columns={'勝敗':'勝率'}))
        trans_h = trans_h.join(self.trans.groupby('H').sum()[['損益(pips)']])
        trans_h = trans_h.join(self.trans[self.trans['勝敗']==1].groupby('H').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均利益(pips/trade)'}))
        trans_h = trans_h.join(self.trans[self.trans['勝敗']==0].groupby('H').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均損失(pips/trade)'}))
        trans_h = trans_h.join(self.trans.groupby('H').max()[['保有期間']].rename(columns={'保有期間':'最大保有期間(h)'}))
        trans_h = trans_h.join(self.trans.groupby('H').min()[['保有期間']].rename(columns={'保有期間':'最小保有期間(h)'}))
        trans_h = trans_h.fillna({'勝トレード数':0,'負トレード数':0,'平均利益(pips/trade)':0,'平均損失(pips/trade)':0})
        trans_h['勝トレード数'] = [int(x) for x in trans_h['勝トレード数']]
        trans_h['負トレード数'] = [int(x) for x in trans_h['負トレード数']]
        trans_h['最大保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_h['最大保有期間(h)']]
        trans_h['最小保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_h['最小保有期間(h)']]
        return trans_h
    # En曜日別サマリ
    def trans_wd(self):
        trans_wd = self.trans.groupby('WD').count()[['決済種別']].rename(columns={'決済種別':'取引回数'})
        trans_wd = trans_wd.join(self.trans.groupby('WD').sum()[['約定']].rename(columns={'約定':'約定回数'}))
        trans_wd = trans_wd.join(self.trans[self.trans['勝敗']==1].groupby('WD').count()[['約定']].rename(columns={'約定':'勝トレード数'}))
        trans_wd = trans_wd.join(self.trans[self.trans['勝敗']==0].groupby('WD').count()[['約定']].rename(columns={'約定':'負トレード数'}))
        trans_wd = trans_wd.join(self.trans.groupby('WD').mean()[['勝敗']].rename(columns={'勝敗':'勝率'}))
        trans_wd = trans_wd.join(self.trans.groupby('WD').sum()[['損益(pips)']])
        trans_wd = trans_wd.join(self.trans[self.trans['勝敗']==1].groupby('WD').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均利益(pips/trade)'}))
        trans_wd = trans_wd.join(self.trans[self.trans['勝敗']==0].groupby('WD').mean()[['損益(pips)']].rename(columns={'損益(pips)':'平均損失(pips/trade)'}))
        trans_wd = trans_wd.join(self.trans.groupby('WD').max()[['保有期間']].rename(columns={'保有期間':'最大保有期間(h)'}))
        trans_wd = trans_wd.join(self.trans.groupby('WD').min()[['保有期間']].rename(columns={'保有期間':'最小保有期間(h)'}))
        trans_wd = trans_wd.fillna({'勝トレード数':0,'負トレード数':0,'平均利益(pips/trade)':0,'平均損失(pips/trade)':0})
        trans_wd['勝トレード数'] = [int(x) for x in trans_wd['勝トレード数']]
        trans_wd['負トレード数'] = [int(x) for x in trans_wd['負トレード数']]
        trans_wd['最大保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_wd['最大保有期間(h)']]
        trans_wd['最小保有期間(h)'] = [x.total_seconds()/(60*60) for x in trans_wd['最小保有期間(h)']]
        return trans_wd

# バックテストレポート読み込み（最適化）
class OptimizeReport:
    def __init__(self,filepath):
        source = open(filepath,'r')
        soup = BeautifulSoup(source,features="html.parser")
        # サマリテーブル読み込み
        sline = soup.findAll("table")[0].findAll("tr")
        self.summary = {}
        self.summary[u'通貨ペア'] = sline[0].findAll("td")[1].string
        self.summary[u'期間'] = sline[1].findAll("td")[1].string
        self.summary[u'モデル'] = sline[2].findAll("td")[1].string
        self.summary[u'初期証拠金'] = float(num_chk(sline[3].findAll("td")[1].string))
        self.summary[u'スプレッド'] = sline[4].findAll("td")[1].string
        # 明細テーブル読み込み
        tline = soup.findAll('table')[1].findAll('tr')
        _cond = list()
        _path = list()
        _pl = list()
        _trans = list()
        _pf = list()
        _gain = list()
        _dd_1 = list()
        _dd_2 = list()
        for l in tline[1:]:
            item = l.findAll('td')
            _cond.append(item[0].get('title'))
            _path.append(item[0].string)
            _pl.append(float(item[1].string))
            _trans.append(int(item[2].string))
            _pf.append(float(item[3].string))
            _gain.append(float(item[4].string))
            _dd_1.append(float(item[5].string))
            _dd_2.append(float(item[6].string))
        self.result = pd.DataFrame({'パス':_path,'条件':_cond,'損益':_pl,'総取引数':_trans,'PF':_pf,'期待利得':_gain,'DD $':_dd_1,'DD %':_dd_2})
        # 条件を分解
        num_conds = len(_cond[0].split('; '))
        for n in range(num_conds-1):
            param_name = _cond[0].split('; ')[n].split('=')[0]
            self.result['P_'+param_name] = [x.split('; ')[n].split('=')[1] for x in self.result['条件']]
        self.result = self.result.drop(['条件'],axis=1)

