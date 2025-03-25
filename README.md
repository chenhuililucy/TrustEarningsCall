# TrustEarningsCall

**Download earnings call dataset from my G-drive:**  
[https://drive.google.com/file/d/1fE38K6rtUSARZEXFIWkFlqbVEwF6WQHi/view?usp=sharing](https://drive.google.com/file/d/1fE38K6rtUSARZEXFIWkFlqbVEwF6WQHi/view?usp=sharing)

本次提供的 Google Drive 文件中，包含了经过实体屏蔽（entity mask）的财报电话会议（earnings transcript）。  
删除其中的组织（org）与个人（person）信息，旨在避免在对数据进行分析时，可能因提前知晓相关组织或个人信息而产生的预判性偏见（*lookahead bias*）。

在使用该数据集时，可依据以下原则进行处理与分析：

1. **引用金融市场回报率（return）**  
   - 依据数据集中给定的 *ticker*、季度（*q*）以及日期（*date*）等信息，对应到参考数据（reference data）中的收盘价格（close price），以此计算从特定 *date* 到 *date + h* 的“收盘到收盘”（close-to-close）回报率。  
   - 该回报率主要用于测度标的股票在指定时间范围内的涨跌幅度。

2. **结合三大财报信息**  
   - 以季度（*q*）为基准，匹配公司所披露的三大财务报表数据（资产负债表、现金流量表、利润表）。  
   - 结合财报数据与实际市场表现（例如上述回报率）相互印证，可用以评估企业在披露财务信息后的市场反应或长期表现。

---

## Reference Data

data 分为：

---
## prices

每家公司的每日股票价格，一般我们会计算T+h的return（如close to close return）。T是earnings call发生的时间。h 是一个未来时间段，如1日，1周，1月等


## 三大报表

公司每个季度都会依据内部财务情况编制三大报表，关键数据可能会在 Earnings Call 前或之后公布。  
为了确保对外披露信息的客观性和一致性，需要针对以下重点字段进行审慎审核，评估管理层在 Earnings Call 中对财务状况、运营成果的陈述是否存在偏颇（unbiased）。

---

### 1. Balance Sheet（资产负债表）

展示公司在特定时点的财务状况，包括资产、负债和股东权益。

- **Total Assets （总资产）**  
  公司拥有或控制的、能为公司带来经济利益的所有资源之和。  

- **Total Liabilities （总负债）**  
  公司因过去的交易或事项而承担的现时义务，需要以资产或服务来偿付。  

- **Shareholder Equity （股东权益）**  
  公司总资产减去总负债后所余的“净值”，代表股东对企业的所有权。  

- **Current Assets & Current Liabilities （流动资产 & 流动负债）**  
  - **流动资产**：预计在一年内或一个营业周期内可以变现或被耗用的资产。  
  - **流动负债**：将在一年内或一个营业周期内需要偿付的负债。

- **Non-Current Liabilities （非流动负债）**  
  一年以上（或超过一个会计周期）到期的负债，也称长期负债。

---

### 2. Cash Flow Statement（现金流量表）

- **Operating Cash Flow（经营活动现金流）**  
  反映公司在日常运营中产生的实际现金流入与流出，通常会与净收益（Net Income）相对比，以评估公司盈利的“含金量”。

- **Capital Expenditures（资本支出，CapEx）**  
  公司在固定资产或长期资产上的支出，可视作对未来成长和竞争力的投资。

- **Free Cash Flow（自由现金流）**  
  被视为企业可以自由支配的现金，对股东分红、股票回购或再投资都至关重要。

- **Cashflow From Financing（筹资活动产生的现金流量）**  
  关注公司通过借款、发行股票或债券获得的现金，以及还本付息或分红、回购股票所流出的现金，也可反映筹资方式及资本结构调整的走向（如发债、增发、回购等）。

- **Dividend Payout & Payments For Repurchase Of Common Stock（股息支付与普通股回购）**  
  体现公司对股东的回报策略；稳定且持续增长的派息或回购通常被视为信心信号，但需考虑是否会对公司现金流造成过度压力。

- **Change In Cash And Cash Equivalents（现金及现金等价物的变动）**  
  衡量公司在一个财务周期内整体现金“进与出”的最终结果，投资者会关注公司是否有充足现金应对近期经营与投资需要。

- **Depreciation, Depletion, And Amortization（折旧、耗竭及摊销）**  
  记于经营活动现金流，非现金成本。常用于评估公司盈利质量及理解利润（EBITDA）与现金流的差异。

- **Change In Operating Assets & Liabilities（经营资产与负债的变动）**  
  包括应收账款、应付账款、存货等变动；其幅度直接影响经营活动现金流，如存货增加太快或应收账款收回不及时，都会压缩现金流。

---

### 3. Income Statement（利润表）

- **Total Revenue (totalRevenue) - [总收入]**  
  企业在特定期间内，通过销售商品或提供服务所获得的总收入，尚未扣除任何费用。  

- **Cost of Revenue / Cost of Goods and Services Sold (costOfRevenue / costofGoodsAndServicesSold) - [收入成本 / 销售成本]**  
  生产商品或提供服务所直接产生的成本。  

- **Gross Profit (grossProfit) - [毛利]**  
  总收入减去收入成本后的差额，体现企业覆盖直接成本后的收益。  

- **Operating Expenses (operatingExpenses) - [营业费用]**  
  企业在日常经营中产生的费用（如销售、管理、研发等），不包含收入成本。  

- **Operating Income (operatingIncome) - [营业利润]**  
  在扣除营业费用后（但尚未扣除利息和税项）企业核心业务所获得的利润。  

- **Income Before Tax (incomeBeforeTax) - [税前利润]**  
  在计提所得税前的利润。  

- **Income Tax Expense (incomeTaxExpense) - [所得税费用]**  
  企业因利润而应支付的所得税金额。  

- **Interest and Debt Expense (interestAndDebtExpense) - [利息及债务费用]**  
  企业因融资而产生的利息及相关债务费用。  

- **Net Income from Continuing Operations (netIncomeFromContinuingOperations) - [持续经营净收益]**  
  企业核心、持续经营业务所获得的净利润。  

- **Comprehensive Income Net of Tax (comprehensiveIncomeNetOfTax) - [税后综合收益]**  
  包含传统净利润及未在净利润中体现的其他收益或损失（如外币折算差额）。  

- **Net Income (netIncome) - [净利润]**  
  企业扣除所有费用、利息与税项后的最终利润。
