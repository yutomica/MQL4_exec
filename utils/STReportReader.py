# 処理名：ストラテジーテスターレポートの読み込み
# encoding = utf-8

import hashlib
import json
import re
from array import array
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from lxml import etree


SCHEMA_VERSION = '1.0.0'
ENTRY_TYPES = {'buy', 'sell'}
EXIT_TYPES = {'close', 's/l', 't/p', 'close at stop'}
KNOWN_EVENT_TYPES = ENTRY_TYPES | EXIT_TYPES | {
    'buy limit', 'sell limit', 'buy stop', 'sell stop', 'modify', 'delete'
}


def _number(indata, field_name, errors, integer=False):
    """数値を変換し、変換不能値を0にせず記録する。"""
    if indata is None or str(indata).strip() == '':
        return np.nan
    value = str(indata).strip().replace(',', '').replace('%', '')
    try:
        number = float(value)
        return int(number) if integer else number
    except (TypeError, ValueError):
        errors.append({'field': field_name, 'value': str(indata), 'error': 'invalid_number'})
        return np.nan


def num_chk(indata):
    """OptimizeReport向けの後方互換関数。"""
    errors = []
    value = _number(indata, 'value', errors)
    return '0' if pd.isna(value) else str(value)


def timedelta_to_DHM(td):
    sec = td.total_seconds()
    return str(int(sec // 86400)) + 'D/' + str(int(sec % 86400 // 3600)) + 'H/' + str(int(sec % 86400 % 3600 // 60)) + 'M'


def _aggregate(trans):
    """全体・期間・セグメントで共通利用する機械的集計。"""
    if trans.empty:
        return {
            'trade_count': 0, 'win_count': 0, 'loss_count': 0, 'breakeven_count': 0,
            'net_profit': 0.0, 'gross_profit': 0.0, 'gross_loss': 0.0,
            'profit_factor': np.nan, 'expectancy': np.nan, 'win_rate': np.nan,
            'average_win': np.nan, 'average_loss': np.nan, 'payoff_ratio': np.nan,
            'pips_total': np.nan, 'pips_mean': np.nan, 'r_total': np.nan, 'r_mean': np.nan,
            'max_profit': np.nan, 'max_loss': np.nan, 'holding_hours_mean': np.nan,
            'holding_hours_median': np.nan, 'holding_hours_max': np.nan,
            'max_drawdown_amount': np.nan, 'max_drawdown_percent': np.nan,
        }

    prof = trans['profit_amount']
    wins = prof[prof > 0]
    losses = prof[prof < 0]
    gross_profit = wins.sum()
    gross_loss = losses.sum()
    cumulative = prof.cumsum()
    initial_balance = trans['balance_after'].iloc[0] - prof.iloc[0]
    balance = initial_balance + cumulative
    peak = pd.concat([pd.Series([initial_balance]), balance.reset_index(drop=True)], ignore_index=True).cummax().iloc[1:].set_axis(balance.index)
    drawdown = peak - balance
    drawdown_percent = drawdown / peak.replace(0, np.nan)

    return {
        'trade_count': int(len(trans)),
        'win_count': int((prof > 0).sum()),
        'loss_count': int((prof < 0).sum()),
        'breakeven_count': int((prof == 0).sum()),
        'net_profit': float(prof.sum()),
        'gross_profit': float(gross_profit),
        'gross_loss': float(gross_loss),
        'profit_factor': float(gross_profit / abs(gross_loss)) if gross_loss else np.nan,
        'expectancy': float(prof.mean()),
        'win_rate': float((prof > 0).mean()),
        'average_win': float(wins.mean()) if not wins.empty else np.nan,
        'average_loss': float(losses.mean()) if not losses.empty else np.nan,
        'payoff_ratio': float(wins.mean() / abs(losses.mean())) if not wins.empty and not losses.empty else np.nan,
        'pips_total': float(trans['pips'].sum(min_count=1)),
        'pips_mean': float(trans['pips'].mean()),
        'r_total': float(trans['r_multiple'].sum(min_count=1)),
        'r_mean': float(trans['r_multiple'].mean()),
        'max_profit': float(prof.max()),
        'max_loss': float(prof.min()),
        'holding_hours_mean': float(trans['holding_hours'].mean()),
        'holding_hours_median': float(trans['holding_hours'].median()),
        'holding_hours_max': float(trans['holding_hours'].max()),
        'max_drawdown_amount': float(drawdown.max()),
        'max_drawdown_percent': float(drawdown_percent.max()),
    }


# バックテストレポート読み込み（最適化なし）
class BacktestReport:
    def __init__(self, filepath, symbol_spec=None):
        self.filepath = Path(filepath)
        if not self.filepath.is_file() or self.filepath.stat().st_size == 0:
            raise FileNotFoundError(f'空ではないバックテストレポートが必要です: {self.filepath}')

        self.parse_errors = []
        self.symbol_spec = symbol_spec
        self.summary_raw = pd.DataFrame()
        self.summary = {}
        self.parameters = pd.DataFrame(columns=['parameter', 'value_raw'])
        self.order_events = pd.DataFrame()
        self.trades = pd.DataFrame()
        self.trans = pd.DataFrame()
        self.validation = {}
        self.metrics = {}
        self.pip_size = np.nan
        self.pip_size_source = None
        self.digits = None

        self._read_report()
        self._build_trades()
        self.validation = self.validate()
        self.metrics = self.build_metrics()

    def _read_report(self):
        """サマリと全注文イベントをHTMLから読み込む。"""
        with self.filepath.open('r', encoding='cp932') as source:
            summary_html = ''
            for line in source:
                summary_html += line
                if '</table>' in line:
                    break

        soup = BeautifulSoup(summary_html, features='lxml')
        tables = soup.find_all('table')
        if not tables:
            raise ValueError(f'サマリテーブルが見つかりません: {self.filepath}')
        sline = [[td.get_text(strip=True) for td in row.find_all('td')] for row in tables[0].find_all('tr')]
        self.summary_raw = pd.DataFrame([
            {'row': no, **{f'cell_{col}': value for col, value in enumerate(item)}}
            for no, item in enumerate(sline)
        ])
        if len(sline) < 20:
            raise ValueError(f'サマリテーブルの行数が不足しています: {len(sline)}')

        period_text = sline[1][1]
        period = re.search(r'\(([A-Z0-9]+)\)', period_text)
        actual_range = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})\s*-\s*(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})', period_text)

        def count_percent(value, field_name):
            match = re.search(r'([-\d,.]+)\s*\(([-\d,.]+)%\)', value or '')
            if not match:
                self.parse_errors.append({'field': field_name, 'value': str(value), 'error': 'invalid_count_percent'})
                return np.nan, np.nan
            return (
                _number(match.group(1), field_name + '_count', self.parse_errors, integer=True),
                _number(match.group(2), field_name + '_percent', self.parse_errors) / 100,
            )

        sell_count, sell_win_rate = count_percent(sline[13][3], 'sell_trades')
        buy_count, buy_win_rate = count_percent(sline[13][5], 'buy_trades')
        win_count, win_rate = count_percent(sline[14][2], 'winning_trades')
        loss_count, _ = count_percent(sline[14][4], 'losing_trades')
        max_dd = re.search(r'([-\d,.]+)\s*\(([-\d,.]+)%\)', sline[11][3])
        if not max_dd:
            self.parse_errors.append({'field': 'max_drawdown', 'value': sline[11][3], 'error': 'invalid_amount_percent'})

        self.summary = {
            'Symbol': sline[0][1],
            '期間': period_text,
            'Period': period.group(1) if period else None,
            'Time_Start': actual_range.group(1) if actual_range else None,
            'Time_End': actual_range.group(2) if actual_range else None,
            'モデル': sline[2][1],
            'パラメーター': sline[3][1],
            'テストバー数': _number(sline[5][1], 'test_bars', self.parse_errors, integer=True),
            '不整合チャートエラー': _number(sline[6][1], 'chart_errors', self.parse_errors, integer=True),
            '初期証拠金': _number(sline[8][1], 'initial_deposit', self.parse_errors),
            'モデルティック数': _number(sline[5][3], 'model_ticks', self.parse_errors, integer=True),
            'モデリング品質': sline[5][5],
            'Spread': sline[8][5],
            '総取引数': _number(sline[13][1], 'total_trades', self.parse_errors, integer=True),
            '取引数（売）': sell_count,
            '取引数（買）': buy_count,
            '純益': _number(sline[9][1], 'net_profit', self.parse_errors),
            '総利益': _number(sline[9][3], 'gross_profit', self.parse_errors),
            '総損失': _number(sline[9][5], 'gross_loss', self.parse_errors),
            '期待利得': _number(sline[10][3], 'expected_payoff', self.parse_errors),
            'プロフィットファクタ': _number(sline[10][1], 'profit_factor', self.parse_errors),
            '最大ドローダウン（金額）': _number(max_dd.group(1), 'max_drawdown_amount', self.parse_errors) if max_dd else np.nan,
            '最大ドローダウン（%）': _number(max_dd.group(2), 'max_drawdown_percent', self.parse_errors) / 100 if max_dd else np.nan,
            '絶対ドローダウン': _number(sline[11][1], 'absolute_drawdown', self.parse_errors),
            '勝率': win_rate,
            '勝率（売）': sell_win_rate,
            '勝率（買）': buy_win_rate,
            '勝トレード数': win_count,
            '負トレード数': loss_count,
            '最大利益': _number(sline[15][2], 'largest_profit_trade', self.parse_errors),
            '最大損失': _number(sline[15][4], 'largest_loss_trade', self.parse_errors),
            '平均利益': _number(sline[16][2], 'average_profit_trade', self.parse_errors),
            '平均損失': _number(sline[16][4], 'average_loss_trade', self.parse_errors),
            '最大連勝数': _number(sline[17][2].split('(')[0], 'max_consecutive_wins', self.parse_errors, integer=True),
            '最大連勝額': _number(sline[17][2].partition('(')[2].rstrip(')'), 'max_consecutive_profit', self.parse_errors),
            '最大連敗数': _number(sline[17][4].split('(')[0], 'max_consecutive_losses', self.parse_errors, integer=True),
            '最大連敗額': _number(sline[17][4].partition('(')[2].rstrip(')'), 'max_consecutive_loss', self.parse_errors),
            '平均連勝数': _number(sline[19][2], 'average_consecutive_wins', self.parse_errors, integer=True),
            '平均連敗数': _number(sline[19][4], 'average_consecutive_losses', self.parse_errors, integer=True),
        }

        parameter_rows = []
        for item in self.summary['パラメーター'].split(';'):
            if '=' in item:
                name, value = item.split('=', 1)
                parameter_rows.append({'parameter': name.strip(), 'value_raw': value.strip()})
        self.parameters = pd.DataFrame(parameter_rows, columns=['parameter', 'value_raw'])

        lst_no, lst_time, lst_order = array('q'), array('q'), array('q')
        lst_vol, lst_price, lst_sl = array('d'), array('d'), array('d')
        lst_tp, lst_prof, lst_zan = array('d'), array('d'), array('d')
        lst_type, lst_status = array('b'), array('b')
        type_names = []
        type_codes = {}
        detail_started = False
        source_row = 0
        max_digits = 0
        for _, row in etree.iterparse(
            str(self.filepath), events=('end',), tag='tr', html=True, recover=True, encoding='cp932'
        ):
            cells = [''.join(td.itertext()).strip() for td in row.xpath('./td')]
            if cells[:3] == ['#', '時間', '取引種別']:
                detail_started = True
            elif detail_started and len(cells) >= 8 and cells[0].strip().isdigit():
                source_row += 1
                cells += [''] * (10 - len(cells))
                status = 'valid'
                try:
                    event_time = datetime.strptime(cells[1], '%Y.%m.%d %H:%M')
                    event_time_value = int((event_time - datetime(1970, 1, 1)).total_seconds() * 1_000_000_000)
                except ValueError:
                    event_time = pd.NaT
                    event_time_value = pd.NaT.value
                    self.parse_errors.append({'field': f'event_time_row_{source_row}', 'value': cells[1], 'error': 'invalid_datetime'})
                    status = 'invalid'
                values = [
                    _number(cells[0], f'event_seq_row_{source_row}', self.parse_errors, integer=True),
                    _number(cells[3], f'ticket_row_{source_row}', self.parse_errors, integer=True),
                    _number(cells[4], f'lots_row_{source_row}', self.parse_errors),
                    _number(cells[5], f'price_row_{source_row}', self.parse_errors),
                    _number(cells[6], f'stop_loss_row_{source_row}', self.parse_errors),
                    _number(cells[7], f'take_profit_row_{source_row}', self.parse_errors),
                    _number(cells[8], f'profit_row_{source_row}', self.parse_errors, integer=False),
                    _number(cells[9], f'balance_row_{source_row}', self.parse_errors, integer=False),
                ]
                if any(pd.isna(value) for value in values[:6]):
                    status = 'invalid'
                lst_no.append(values[0])
                lst_time.append(event_time_value)
                event_type = cells[2].strip().lower()
                if event_type not in type_codes:
                    type_codes[event_type] = len(type_names)
                    type_names.append(event_type)
                lst_type.append(type_codes[event_type])
                lst_order.append(values[1])
                lst_vol.append(values[2])
                lst_price.append(values[3])
                lst_sl.append(values[4])
                lst_tp.append(values[5])
                lst_prof.append(values[6])
                lst_zan.append(values[7])
                lst_status.append(0 if status == 'valid' else 1)
                if '.' in cells[5]:
                    max_digits = max(max_digits, len(cells[5].partition('.')[2]))
            row.clear()
            while row.getprevious() is not None:
                del row.getparent()[0]

        if not lst_no:
            raise ValueError(f'注文イベントが見つかりません: {self.filepath}')

        self.order_events = pd.DataFrame({
            'event_seq': np.asarray(lst_no),
            'event_time': pd.to_datetime(np.asarray(lst_time)),
            'event_type': pd.Categorical.from_codes(np.asarray(lst_type), categories=type_names),
            'ticket': np.asarray(lst_order),
            'lots': np.asarray(lst_vol),
            'price': np.asarray(lst_price),
            'stop_loss': np.asarray(lst_sl),
            'take_profit': np.asarray(lst_tp),
            'profit': np.asarray(lst_prof),
            'balance': np.asarray(lst_zan),
            'source_row': range(1, len(lst_no) + 1),
            'parse_status': pd.Categorical.from_codes(np.asarray(lst_status), categories=['valid', 'invalid']),
        })

        if isinstance(self.symbol_spec, dict):
            self.pip_size = self.symbol_spec.get('pip_size', np.nan)
            self.digits = self.symbol_spec.get('digits')
            self.pip_size_source = 'symbol_spec' if pd.notna(self.pip_size) else None
        elif self.symbol_spec is not None:
            self.pip_size = float(self.symbol_spec)
            self.pip_size_source = 'argument'

        if pd.isna(self.pip_size):
            if max_digits:
                self.digits = max_digits
                self.pip_size = 10 ** (-(self.digits - 1)) if self.digits in (3, 5) else 10 ** (-self.digits)
                self.pip_size_source = 'inferred_digits'

    def _build_trades(self):
        """注文番号ごとの状態遷移から決済済み取引だけを生成する。"""
        orders = {}
        for event in self.order_events.itertuples(index=False):
            item = orders.setdefault(event.ticket, {
                'entry': None, 'exit': None, 'entry_count': 0, 'exit_count': 0,
                'modify_count': 0, 'last_stop_loss': np.nan, 'last_take_profit': np.nan,
                'last_type': None,
            })
            item['last_type'] = event.event_type
            if event.event_type in ENTRY_TYPES:
                item['entry_count'] += 1
                if item['entry'] is None:
                    item['entry'] = event
                    item['last_stop_loss'] = event.stop_loss
                    item['last_take_profit'] = event.take_profit
            elif item['entry'] is not None and event.event_type == 'modify':
                item['modify_count'] += 1
                item['last_stop_loss'] = event.stop_loss
                item['last_take_profit'] = event.take_profit
            elif item['entry'] is not None and event.event_type in EXIT_TYPES:
                item['exit_count'] += 1
                item['exit'] = event
                item['last_stop_loss'] = event.stop_loss
                item['last_take_profit'] = event.take_profit

        trans = []
        unresolved = []
        for ticket, item in orders.items():
            _open = item['entry']
            _close = item['exit']
            if _open is None:
                if item['last_type'] != 'delete':
                    unresolved.append(int(ticket))
                continue
            if _close is None:
                unresolved.append(int(ticket))
                continue

            direction = _open.event_type
            price_move = _close.price - _open.price if direction == 'buy' else _open.price - _close.price
            risk_price = _open.price - _open.stop_loss if direction == 'buy' else _open.stop_loss - _open.price
            risk_price = risk_price if risk_price > 0 else np.nan
            pips = price_move / self.pip_size if pd.notna(self.pip_size) and self.pip_size > 0 else np.nan
            risk_pips = risk_price / self.pip_size if pd.notna(risk_price) and pd.notna(self.pip_size) and self.pip_size > 0 else np.nan
            r_multiple = price_move / risk_price if pd.notna(risk_price) else np.nan
            profit = _close.profit
            flags = []
            if item['entry_count'] != 1:
                flags.append('multiple_entries')
            if item['exit_count'] != 1:
                flags.append('multiple_exits')
            if pd.isna(profit) or pd.isna(_close.balance):
                flags.append('missing_exit_value')
            if not np.isclose(_open.lots, _close.lots):
                flags.append('volume_mismatch')
            if pd.isna(risk_price):
                flags.append('invalid_initial_risk')

            holding_seconds = (_close.event_time - _open.event_time).total_seconds()
            trans.append({
                'ticket': int(ticket),
                'entry_event_seq': int(_open.event_seq),
                'exit_event_seq': int(_close.event_seq),
                'direction': direction,
                'entry_time': _open.event_time,
                'entry_price': _open.price,
                'entry_lots': _open.lots,
                'initial_stop_loss': _open.stop_loss,
                'initial_take_profit': _open.take_profit,
                'exit_time': _close.event_time,
                'exit_price': _close.price,
                'exit_lots': _close.lots,
                'exit_reason': _close.event_type,
                'profit_amount': profit,
                'balance_after': _close.balance,
                'holding_seconds': holding_seconds,
                'holding_hours': holding_seconds / 3600,
                'price_move': price_move,
                'pips': pips,
                'initial_risk_price': risk_price,
                'initial_risk_pips': risk_pips,
                'r_multiple': r_multiple,
                'result': 'win' if profit > 0 else ('loss' if profit < 0 else 'breakeven'),
                'modify_count': item['modify_count'],
                'last_stop_loss': item['last_stop_loss'],
                'last_take_profit': item['last_take_profit'],
                'remaining_lots': max(_open.lots - _close.lots, 0),
                'possible_partial_close': not np.isclose(_open.lots, _close.lots),
                'entry_year': _open.event_time.strftime('%Y'),
                'entry_month': _open.event_time.strftime('%Y-%m'),
                'entry_weekday': int(_open.event_time.weekday() + 1),
                'entry_hour': _open.event_time.strftime('%H'),
                'exit_year': _close.event_time.strftime('%Y'),
                'exit_month': _close.event_time.strftime('%Y-%m'),
                'exit_weekday': int(_close.event_time.weekday() + 1),
                'exit_hour': _close.event_time.strftime('%H'),
                'data_quality_flags': ';'.join(flags),
            })

        self.unresolved_tickets = unresolved
        self.trades = pd.DataFrame(trans).sort_values('exit_event_seq').reset_index(drop=True)
        if self.trades.empty:
            raise ValueError(f'決済済み取引が見つかりません: {self.filepath}')

        # Backtest.pyと既存利用箇所の互換性を保つ。
        self.trans = pd.DataFrame({
            '約定種別': self.trades['direction'],
            '数量': self.trades['entry_lots'],
            '約定日時': self.trades['entry_time'],
            '約定価格': self.trades['entry_price'],
            '決済逆指値(S/L)': self.trades['initial_stop_loss'],
            '決済指値(T/P)': self.trades['initial_take_profit'],
            '決済種別': self.trades['exit_reason'],
            '決済日時': self.trades['exit_time'],
            '決済価格': self.trades['exit_price'],
            '損益': self.trades['profit_amount'],
            '残高': self.trades['balance_after'],
            '変更回数': self.trades['modify_count'],
            '約定': 1,
            '損益(pips)': self.trades['pips'],
            'Risk': self.trades['initial_risk_price'],
            'Profit': self.trades['price_move'],
            'R': self.trades['r_multiple'],
            '勝敗': self.trades['result'].map({'win': 1.0, 'loss': 0.0, 'breakeven': np.nan}),
            '結果': self.trades['result'],
            '保有期間': pd.to_timedelta(self.trades['holding_seconds'], unit='s'),
            'YYYYMM': self.trades['exit_month'],
            'YYYY': self.trades['exit_year'],
            'H': self.trades['entry_hour'],
            'WD': self.trades['entry_weekday'].map({
                1: '1:月', 2: '2:火', 3: '3:水', 4: '4:木', 5: '5:金', 6: '6:土', 7: '7:日'
            }),
        })
        self.trans.index = pd.Index(self.trades['ticket'].to_numpy(), name='注文番号')

    def validate(self):
        checks = []

        def add_check(name, expected, actual, tolerance=0, required=True):
            if pd.isna(expected) or pd.isna(actual):
                status = 'invalid' if required else 'warning'
                difference = None
            else:
                difference = float(actual - expected)
                status = 'valid' if abs(difference) <= tolerance else ('invalid' if required else 'warning')
            checks.append({
                'name': name,
                'expected': None if pd.isna(expected) else float(expected),
                'actual': None if pd.isna(actual) else float(actual),
                'difference': difference,
                'status': status,
            })

        prof = self.trades['profit_amount']
        add_check('trade_count', self.summary['総取引数'], len(self.trades))
        add_check('sell_count', self.summary['取引数（売）'], (self.trades['direction'] == 'sell').sum())
        add_check('buy_count', self.summary['取引数（買）'], (self.trades['direction'] == 'buy').sum())
        # MT4は損益0を勝トレード側へ含めるため、非損失件数で照合する。
        add_check('mt4_winning_trade_count', self.summary['勝トレード数'], (prof >= 0).sum())
        add_check('losing_trade_count', self.summary['負トレード数'], (prof < 0).sum())
        add_check('net_profit', self.summary['純益'], prof.sum(), tolerance=0.01)
        add_check('gross_profit', self.summary['総利益'], prof[prof > 0].sum(), tolerance=0.01)
        add_check('gross_loss', self.summary['総損失'], prof[prof < 0].sum(), tolerance=0.01)
        add_check('ending_balance', self.summary['初期証拠金'] + self.summary['純益'], self.trades['balance_after'].iloc[-1], tolerance=0.01)
        recomputed = _aggregate(self.trades)
        add_check('profit_factor', self.summary['プロフィットファクタ'], recomputed['profit_factor'], tolerance=0.01)
        add_check('reported_vs_closed_balance_drawdown', self.summary['最大ドローダウン（金額）'], recomputed['max_drawdown_amount'], tolerance=0.01, required=False)
        add_check('event_sequence_unique', len(self.order_events), self.order_events['event_seq'].nunique())
        add_check(
            'event_sequence_contiguous',
            self.order_events['event_seq'].iloc[-1] - self.order_events['event_seq'].iloc[0] + 1,
            len(self.order_events),
        )
        # MT4は部分決済等を分単位表示するため、event_seqを正本とし時刻逆転は警告に留める。
        add_check('event_time_order', 1, int(self.order_events['event_time'].is_monotonic_increasing), required=False)

        unknown_types = sorted(set(self.order_events['event_type']) - KNOWN_EVENT_TYPES)
        errors = list(self.parse_errors)
        if unknown_types:
            errors.append({'field': 'event_type', 'value': unknown_types, 'error': 'unknown_event_type'})
        if (self.order_events['parse_status'] == 'invalid').any():
            errors.append({'field': 'order_events', 'value': int((self.order_events['parse_status'] == 'invalid').sum()), 'error': 'invalid_rows'})
        critical_flags = self.trades['data_quality_flags'].str.contains('multiple_entries|multiple_exits|missing_exit_value', regex=True)
        if critical_flags.any():
            errors.append({'field': 'trades', 'value': int(critical_flags.sum()), 'error': 'invalid_state_transition'})

        status = 'invalid' if errors or any(item['status'] == 'invalid' for item in checks) else 'valid'
        warnings = []
        if self.unresolved_tickets:
            warnings.append({'field': 'unresolved_tickets', 'count': len(self.unresolved_tickets), 'tickets': self.unresolved_tickets})
        if self.pip_size_source == 'inferred_digits':
            warnings.append({'field': 'pip_size', 'value': self.pip_size, 'warning': 'inferred_from_price_digits'})
        if any(item['status'] == 'warning' for item in checks):
            warnings.append({'field': 'drawdown', 'warning': 'reported_and_closed_balance_drawdown_differ'})
        if status == 'valid' and warnings:
            status = 'warning'

        return {
            'schema_version': SCHEMA_VERSION,
            'status': status,
            'checks': checks,
            'errors': errors,
            'warnings': warnings,
            'event_count': int(len(self.order_events)),
            'trade_count': int(len(self.trades)),
            'unresolved_ticket_count': len(self.unresolved_tickets),
            'pip_size': None if pd.isna(self.pip_size) else self.pip_size,
            'pip_size_source': self.pip_size_source,
            'digits': self.digits,
        }

    def build_metrics(self):
        overall = pd.DataFrame([_aggregate(self.trades)])

        period_rows = []
        period_values = {
            'year': self.trades['exit_time'].dt.to_period('Y').astype(str),
            'quarter': self.trades['exit_time'].dt.to_period('Q').astype(str),
            'month': self.trades['exit_time'].dt.to_period('M').astype(str),
        }
        for period_type, values in period_values.items():
            for period_key, item in self.trades.groupby(values, sort=True):
                period_rows.append({
                    'period_type': period_type,
                    'period_key': period_key,
                    'period_start': item['exit_time'].min(),
                    'period_end': item['exit_time'].max(),
                    **_aggregate(item),
                })
        period_metrics = pd.DataFrame(period_rows)

        segment_rows = []
        segments = {
            'direction': self.trades['direction'],
            'entry_hour': self.trades['entry_hour'],
            'entry_weekday': self.trades['entry_weekday'],
            'exit_reason': self.trades['exit_reason'],
            'holding_bucket': pd.cut(
                self.trades['holding_hours'],
                bins=[-np.inf, 1, 6, 24, 72, np.inf],
                labels=['0-1h', '1-6h', '6-24h', '24-72h', '72h+'],
            ),
        }
        for segment_type, values in segments.items():
            for segment_value, item in self.trades.groupby(values, observed=True, sort=True):
                segment_rows.append({
                    'segment_type': segment_type,
                    'segment_value': str(segment_value),
                    **_aggregate(item),
                })
        segment_metrics = pd.DataFrame(segment_rows)

        distribution_rows = []
        for metric in ['profit_amount', 'pips', 'r_multiple', 'holding_hours']:
            values = self.trades[metric].dropna()
            distribution_rows.append({
                'metric': metric,
                'count': int(values.count()),
                'mean': values.mean(),
                'std': values.std(),
                'min': values.min(),
                'q01': values.quantile(0.01),
                'q05': values.quantile(0.05),
                'q25': values.quantile(0.25),
                'median': values.median(),
                'q75': values.quantile(0.75),
                'q95': values.quantile(0.95),
                'q99': values.quantile(0.99),
                'max': values.max(),
            })
        distribution = pd.DataFrame(distribution_rows)

        drawdown_rows = []
        peak_balance = self.summary['初期証拠金']
        peak_time = pd.NaT
        start_time = pd.NaT
        trough_time = pd.NaT
        max_amount = 0.0
        episode = 0
        for item in self.trades.itertuples(index=False):
            if item.balance_after >= peak_balance:
                if pd.notna(start_time):
                    drawdown_rows.append({
                        'episode': episode,
                        'start_time': start_time,
                        'trough_time': trough_time,
                        'recovery_time': item.exit_time,
                        'drawdown_amount': max_amount,
                        'drawdown_percent': max_amount / peak_balance if peak_balance else np.nan,
                        'recovered': True,
                    })
                    start_time = pd.NaT
                    max_amount = 0.0
                peak_balance = item.balance_after
                peak_time = item.exit_time
            else:
                if pd.isna(start_time):
                    episode += 1
                    start_time = peak_time if pd.notna(peak_time) else self.trades['entry_time'].iloc[0]
                amount = peak_balance - item.balance_after
                if amount > max_amount:
                    max_amount = amount
                    trough_time = item.exit_time
        if pd.notna(start_time):
            drawdown_rows.append({
                'episode': episode,
                'start_time': start_time,
                'trough_time': trough_time,
                'recovery_time': pd.NaT,
                'drawdown_amount': max_amount,
                'drawdown_percent': max_amount / peak_balance if peak_balance else np.nan,
                'recovered': False,
            })
        drawdowns = pd.DataFrame(drawdown_rows)

        streak_rows = []
        current_result = None
        current_start = None
        current_profit = 0.0
        current_count = 0
        for item in self.trades.itertuples(index=False):
            if item.result != current_result:
                if current_result is not None:
                    streak_rows.append({
                        'result': current_result, 'start_time': current_start,
                        'end_time': previous_time, 'count': current_count, 'profit': current_profit,
                    })
                current_result = item.result
                current_start = item.exit_time
                current_profit = 0.0
                current_count = 0
            current_profit += item.profit_amount
            current_count += 1
            previous_time = item.exit_time
        streak_rows.append({
            'result': current_result, 'start_time': current_start,
            'end_time': previous_time, 'count': current_count, 'profit': current_profit,
        })
        streaks = pd.DataFrame(streak_rows)

        sorted_profit = self.trades['profit_amount'].sort_values(ascending=False)
        gross_profit = sorted_profit[sorted_profit > 0].sum()
        concentration = pd.DataFrame([{
            'top_1_profit_share': sorted_profit.head(1).sum() / gross_profit if gross_profit else np.nan,
            'top_5_profit_share': sorted_profit.head(5).sum() / gross_profit if gross_profit else np.nan,
            'top_10_profit_share': sorted_profit.head(10).sum() / gross_profit if gross_profit else np.nan,
            'net_profit_without_top_1': sorted_profit.iloc[1:].sum(),
            'net_profit_without_top_5': sorted_profit.iloc[5:].sum(),
            'net_profit_without_top_10': sorted_profit.iloc[10:].sum(),
        }])

        return {
            'overall': overall,
            'period_metrics': period_metrics,
            'segment_metrics': segment_metrics,
            'distribution': distribution,
            'drawdowns': drawdowns,
            'streaks': streaks,
            'concentration': concentration,
        }

    def export(self, output_dir, run_metadata=None):
        """正規化データ、定型集計、検証結果、manifestを出力する。"""
        output_dir = Path(output_dir)
        normalized_dir = output_dir / 'normalized'
        analysis_dir = output_dir / 'analysis'
        targets = [
            normalized_dir / 'order_events.csv.gz',
            normalized_dir / 'trades.csv.gz',
            analysis_dir / 'metrics.xlsx',
            output_dir / 'validation.json',
            output_dir / 'manifest.json',
        ]
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            raise FileExistsError(f'既存成果物を上書きしません: {existing}')
        normalized_dir.mkdir(parents=True, exist_ok=True)
        analysis_dir.mkdir(parents=True, exist_ok=True)

        self.order_events.to_csv(
            targets[0], index=False, encoding='utf-8', date_format='%Y-%m-%dT%H:%M:%S',
            compression={'method': 'gzip', 'mtime': 0},
        )
        self.trades.to_csv(
            targets[1], index=False, encoding='utf-8', date_format='%Y-%m-%dT%H:%M:%S',
            compression={'method': 'gzip', 'mtime': 0},
        )

        quality_rows = self.validation['checks'] + self.validation['errors'] + self.validation['warnings']
        with pd.ExcelWriter(targets[2]) as excel_writer:
            pd.DataFrame([run_metadata or {}]).to_excel(excel_writer, sheet_name='run_metadata', index=False)
            pd.DataFrame(quality_rows).to_excel(excel_writer, sheet_name='data_quality', index=False)
            for sheet_name, data in self.metrics.items():
                data.to_excel(excel_writer, sheet_name=sheet_name, index=False)
            self.trades.to_excel(excel_writer, sheet_name='trades', index=False)

        def json_default(value):
            if isinstance(value, (datetime, pd.Timestamp)):
                return value.isoformat()
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, (np.integer, np.floating)):
                return value.item()
            if isinstance(value, np.bool_):
                return bool(value)
            raise TypeError(f'JSONへ変換できない値です: {type(value)}')

        def json_clean(value):
            if isinstance(value, dict):
                return {key: json_clean(item) for key, item in value.items()}
            if isinstance(value, list):
                return [json_clean(item) for item in value]
            if isinstance(value, (float, np.floating)) and pd.isna(value):
                return None
            return value

        targets[3].write_text(
            json.dumps(json_clean(self.validation), ensure_ascii=False, indent=2, allow_nan=False, default=json_default),
            encoding='utf-8',
        )
        report_hash = hashlib.sha256()
        with self.filepath.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                report_hash.update(block)
        manifest = {
            'schema_version': SCHEMA_VERSION,
            'run_metadata': run_metadata or {},
            'report': {
                'path': str(self.filepath.resolve()),
                'size': self.filepath.stat().st_size,
                'sha256': report_hash.hexdigest(),
            },
            'summary': self.summary,
            'parameters': self.parameters.to_dict(orient='records'),
            'validation_status': self.validation['status'],
            'artifacts': [str(path.relative_to(output_dir)) for path in targets[:4]],
        }
        targets[4].write_text(
            json.dumps(json_clean(manifest), ensure_ascii=False, indent=2, allow_nan=False, default=json_default),
            encoding='utf-8',
        )

        for path in targets:
            if not path.is_file() or path.stat().st_size == 0:
                raise IOError(f'成果物の出力確認に失敗しました: {path}')
        return {path.name: path for path in targets}

    def _legacy_metrics(self, metric_type, metric_name):
        if metric_type == 'period':
            data = self.metrics['period_metrics']
            data = data[data['period_type'] == metric_name].set_index('period_key')
        else:
            data = self.metrics['segment_metrics']
            data = data[data['segment_type'] == metric_name].set_index('segment_value')
        result = pd.DataFrame(index=data.index)
        result['取引回数'] = data['trade_count']
        result['約定回数'] = data['trade_count']
        result['勝トレード数'] = data['win_count']
        result['負トレード数'] = data['loss_count']
        result['勝率'] = data['win_rate']
        result['損益(pips)'] = data['pips_total']
        group_values = (
            self.trades['exit_year'] if metric_name == 'year' else
            self.trades['exit_month'] if metric_name == 'month' else
            self.trades['entry_hour'] if metric_name == 'entry_hour' else self.trades['entry_weekday'].astype(str)
        )
        legacy = self.trades.assign(_group=group_values)
        result['平均利益(pips/trade)'] = legacy[legacy['result'] == 'win'].groupby('_group')['pips'].mean().reindex(result.index)
        result['平均損失(pips/trade)'] = legacy[legacy['result'] == 'loss'].groupby('_group')['pips'].mean().reindex(result.index)
        result['最大保有期間(h)'] = data['holding_hours_max']
        result['最小保有期間(h)'] = legacy.groupby('_group')['holding_hours'].min().reindex(result.index)
        return result

    # 既存API互換
    def trans_y(self):
        return self._legacy_metrics('period', 'year')

    def trans_ym(self):
        return self._legacy_metrics('period', 'month')

    def trans_h(self):
        return self._legacy_metrics('segment', 'entry_hour')

    def trans_wd(self):
        return self._legacy_metrics('segment', 'entry_weekday')


# バックテストレポート読み込み（最適化）
class OptimizeReport:
    def __init__(self,filepath):
        with open(filepath,'r',encoding='cp932') as source:
            soup = BeautifulSoup(source,features="lxml")
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
