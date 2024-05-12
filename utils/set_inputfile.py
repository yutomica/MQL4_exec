# MT4入力ファイル作成関数
# TestModel 0:EveryTick 1:ControlPoint

# 通常のバックテスト用
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

# 最適化用
def set_inputfile_opt(st_name,symbol,period,mode,opt_tf,setfile_nm,date_from,date_to,outfile):
        text = "TestExpert="+st_name+"\n" \
        +"TestExpertParameters="+setfile_nm+"\n" \
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