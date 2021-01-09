import pandas as pd
import Binance
import math
from talib import EMA, ATR, RSI, TRIX, MA

def floatPrecision(f, n):
	n = int(math.log10(1 / float(n)))
	f = math.floor(float(f) * 10 ** n) / 10 ** n
	f = "{:0.0{}f}".format(float(f), n)
	return str(int(f)) if int(n) == 0 else f

def decimalize(n):
	if n == 1:
		t = 0.1
	elif n == 0: 
		t = 1
	else:
		q = '{0:.' + '{}'.format(n-1) +'f}'
		t = str.format(q, 0) + '1'
	return float(t)

class start:
	def __init__(self, symbol, quote, step_size, leverage, interval, roundQuant, total_quant):
		self.symbol = symbol
		self.quote = quote
		self.base = symbol[:-4]
		self.step_size = step_size
		self.leverage = leverage
		self.interval = interval
		self.roundQuant = roundQuant
		self.total_quant = total_quant
		self.pos = self.position()
		self.openPosition = float(Binance.client.futures_position_information()[self.pos]['positionAmt'])
		self.entryPrice = float(Binance.client.futures_position_information()[self.pos]['entryPrice'])
		self.df = self.getData()
		self.changeLeverage = self.changeLeverage()
		self.quoteBalance = float(Binance.client.futures_account_balance()[0]['balance'])
		self.Quant = self.checkQuant()
		self.fire = self.strategy()

	def position(self):
		p = Binance.client.futures_position_information()
		for i in p:
			if i['symbol'] == self.symbol:
				return p.index(i)

	def getData(self):
		candles = Binance.client.futures_klines(symbol=self.symbol, interval=self.interval)

		#Sorting candlestick using Pandas
		df = pd.DataFrame(candles)
		df = df.drop(range(6, 12), axis=1)

		# put in dataframe and clean-up
		col_names = ['time', 'open', 'high', 'low', 'close', 'volume']
		df.columns = col_names
		# transform values from strings to floats
		for col in col_names:
			df[col] = df[col].astype(float)

		return df

	def changeLeverage(self):
		def change():
			change = Binance.client.futures_change_leverage(
				symbol=self.symbol,
				leverage=self.leverage)
		return change()
	
	def checkQuant(self):
		df = self.df
		canBuySell = (float(self.quoteBalance)/float(df['close'].iloc[-1]))*self.total_quant*self.leverage
		BuySellQuant = floatPrecision(canBuySell, self.roundQuant)
		return BuySellQuant

	def getData(self):
		candles = Binance.client.futures_klines(symbol=self.symbol, interval=self.interval)

		#Sorting candlestick using Pandas
		df = pd.DataFrame(candles)
		df = df.drop(range(6, 12), axis=1)

		# put in dataframe and clean-up
		col_names = ['time', 'open', 'high', 'low', 'close', 'volume']
		df.columns = col_names
		# transform values from strings to floats
		for col in col_names:
			df[col] = df[col].astype(float)

		return df

	def strategy(self):

		df = self.df
		"""Prepare indicators for strategy"""
		baseline = MA(df['close'], timeperiod=100)
		baseline = float(baseline[499])

		atr = ATR(df['high'], df['low'], df['close'], timeperiod=14)
		atr = float(atr[499])

		trix = TRIX(df['close'], timeperiod=20)
		tx = float(trix[499])*100

		blue = EMA(df['close'], timeperiod=7)
		tema = TRIX(blue, timeperiod=20)
		tema = float(tema[499])*100

		low = float(floatPrecision(df['low'][499], self.step_size))
		high = float(floatPrecision(df['high'][499], self.step_size))

		current = float(floatPrecision(df['close'][499], self.step_size))

		longSL = float(floatPrecision((baseline - atr), self.step_size))
		longTP = float(floatPrecision((current + atr*3), self.step_size))
		shortSL = float(floatPrecision((baseline + atr), self.step_size))
		shortTP = float(floatPrecision((current - atr*3), self.step_size))

		def clearOrders():
			order = Binance.client.futures_cancel_all_open_orders(
				symbol = self.symbol)
			
		def closeSellOrder():
			orderBuy = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'BUY',
				type = 'MARKET',
				quantity = self.baseBalance,
				reduceOnly='true')
			
		def closeBuyOrder():
			orderSell = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'SELL',
				type = 'MARKET',
				quantity = self.baseBalance,
				reduceOnly='true')
			
		def placeSellOrder():
			orderSell = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'SELL',
				type = 'MARKET',
				quantity = self.Quant)

		def placeBuyOrder():
			orderBuy = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'BUY',
				type = 'MARKET',
				quantity = self.Quant)
			
		def longStop():
			order = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'SELL',
				type = 'STOP_MARKET',
				stopPrice = longSL,
				closePosition='true')
			
		def shortStop():
			order = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'BUY',
				type = 'STOP_MARKET',
				stopPrice = shortSL,
				closePosition='true')
			
		def longProfit():
			order = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'SELL',
				type = 'TAKE_PROFIT_MARKET',
				stopPrice = longTP,
				closePosition='true')
			
		def shortProfit():
			order = Binance.client.futures_create_order(
				symbol = self.symbol,
				side = 'BUY',
				type = 'TAKE_PROFIT_MARKET',
				stopPrice = shortTP,
				closePosition='true')

		"""Set up your strategy here 
		Conditions for trading"""

		longCond = current > baseline and tx > tema and self.openPosition == 0
		closeLong = tx < tema and self.openPosition > 0
		shortCond = current < baseline and tx < tema and self.openPosition == 0
		closeShort = tx > tema and self.openPosition < 0
		#############################################

		while longCond == True:
			try:
				clearOrders()
				placeBuyOrder()
				longStop()
				print('Long order opened on', self.symbol)
				break
			except:
				break

		while shortCond == True:
			try:
				clearOrders()
				placeSellOrder()
				shortStop()
				print('Short order opened on', self.symbol)
				break
			except:
				break
			
		while closeLong == True:
			try:
				closeBuyOrder()
				clearOrders()
				print('Long order closed on', self.symbol)
				break
			except:
				break

		while closeShort == True:
			try:
				closeSellOrder()
				clearOrders()
				print('Short order closed on', self.symbol)
				break
			except:
				break

"""Scan and place order for all symbols available on market
WARNING: This option may triggering liquidation if you don't have a clear 
capital management strategy or your account is too small,
better go with 1 or 2 symbol if you are a beginner
"""
# OPTION 1
#def run():
#    quote = 'USDT'
#    leverage = 20
#    interval = '15m'
#    total_quant = 0.002 """Number of you total account in percentage that you allowed for trade, this default number worth 0.2% of you CURRENT account
#                           it's getting smaller and smaller everytime an order placed"""

#    t = Binance.client.futures_exchange_info()

#    for i in t['symbols']:
#        if i['symbol'].endswith(quote):
#            start(i['symbol'], quote, decimalize(i['pricePrecision']), leverage, interval, decimalize(i['quantityPrecision']), total_quant)

# OPTION 2
def run():
	tlist = ['BTCUSDT', 'TRXUSDT']
	quote = 'USDT'
	leverage = 20 #Don't try to change this to higher, x20 leverage is way too risky
	interval = '15m'
	total_quant = 0.002 #Number of total amount in percentage that you allowed for trade, this default number worth 0.2%\ of you CURRENT account
						#   it's getting smaller and smaller everytime an order placed

	t = Binance.client.futures_exchange_info()

	for i in t['symbols']:
		for j in tlist:
			if i['symbol'] == j:
				start(i['symbol'], quote, decimalize(i['pricePrecision']), leverage, interval, decimalize(i['quantityPrecision']), total_quant)

