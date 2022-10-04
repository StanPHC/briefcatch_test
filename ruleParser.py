import pandas as pd
import os
import re
import string

posFileName = 'ruleParser.pos.mapping.xlsx'
dfPOS = pd.read_excel(os.path.join(os.getcwd(),posFileName),sheet_name='posMAP')


def isPOSformat(tok):
	ismulti = tok.endswith('.*?')
	noregexpos = tok.replace('.*?','').replace(':','')
	if noregexpos.isalpha() and noregexpos.isupper():
		return True
	else:
		return False

def mapPOS(postag):
	if not isPOSformat(postag):
		return []
	else:
		ismulti = postag.endswith('.*?')
		queryTag = postag.replace('.*?','')
		if ismulti == True:
			results = dfPOS.query('bcPOS.str.startswith(@queryTag)')
		else:
			results = dfPOS.query('bcPOS== @queryTag')
		xpos = results['xPOS'].tolist()
		return xpos

def tagPOS(atok):
	itemlist = []
	if type(atok) is list:
		itemlist.extend(atok)
	else:
		itemlist.append(atok)

	postaggedlist = []
	for item in itemlist:
		taglist = mapPOS(item)
		if len(taglist) > 0:
			for tag in taglist:
				postaggedlist.append('_POS_#_'+tag)
		else:
			postaggedlist.append(item)
	postaggedlist = list(dict.fromkeys(postaggedlist))
	return postaggedlist

def getList(lst):
	items = []
	for x in lst:
		if x == ')':
			break
		items.append(x)
	return items

def ct2lemma(rule):
	pattern = r'CT\s*\(\s*[a-zA-Z]+\s*\)'
	newRule = rule
	CTs = re.findall(pattern,rule)
	for ct in CTs:
		elts = ct.split(' ')
		word = elts[2]
		newStr = ' _LEMMA_#_'+word+' '
		newRule = newRule.replace(ct,newStr)
	return newRule

def handleSKIP(ruleStr):
	toklist = ruleStr.split(' ')
	newtoklist = []
	for tok in toklist:
		if tok.startswith('SKIP') and tok[4:].isnumeric(): #re.search(r'SKIP\d+',tok)
			skipCount = int(tok.replace('SKIP',''))
			skipString = []
			for i in range(0,skipCount):
				addtok = '(_ANY_TOKEN_ )'
				skipString.append(addtok)
			newtoklist.append(' '.join(skipString))
		else:
			newtoklist.append(tok)
	return ' '.join(newtoklist)

def parseRule(rule):
	toks = {}
	tokCount = 0
	ruleNorm = rule.replace('RX([a-zA-Z]*)','_ANY_TOKEN_') # RX([a-zA-Z]*)
	ruleNorm = ruleNorm.replace('RX([A-Za-z]*)','_ANY_TOKEN_')
	ruleNorm = ruleNorm.replace('RX([a-zA-Z]+)','_ANY_TOKEN_')
	ruleNorm = ruleNorm.replace('RX([A-Za-z]+)','_ANY_TOKEN_')
	ruleNorm = ruleNorm.replace('RX(.*?)','_ANY_TOKEN_')
	ruleNorm = ruleNorm.replace('\\','')
	ruleNorm = handleSKIP(ruleNorm)
	ruleNorm = re.sub(r'\(',' ( ',ruleNorm)
	ruleNorm = re.sub(r'\)',' ) ',ruleNorm)
	ruleNorm = re.sub(r'\s+',' ',ruleNorm)
	ruleNorm = ruleNorm.strip()
	ruleNorm = ct2lemma(ruleNorm)
	ruleNorm = re.sub(r'\s+',' ',ruleNorm)
	ruleNorm = ruleNorm.strip()
	
	######################################## print('Normalized:', ruleNorm)
	elts = ruleNorm.split(' ')
	newRule = []
	lemmatize = []
	listify = []

	i = 0
	while i < len(elts):
		e = elts[i]
		if e == '(':
			alist = getList(elts[i+1:])
			listify.append(alist)
			toks[tokCount] = alist
			tokCount+= 1
			i = i+ len(alist)+1
		else:
			toks[tokCount] = e
			tokCount += 1
		i = i+1
	parsedToks = {}
	for k in toks:
		atok = tagPOS(toks[k])
		tokID = str(k)
		if type(atok) is list and atok[-1] == '~':
			tokID = tokID+'~'
			parsedToks[tokID] = atok[:-1]
		else:
			parsedToks[tokID] = atok

	return parsedToks

def ruleParser(rstring):
	rule = rstring
	#print(rule)
	#print('\n--------------------------------------------------')
	parsedDict = parseRule(rule)
	#for k in parsedDict:
	#	print(k, parsedDict[k])
	#print('\n--------------------------------------------------')

	return parsedDict

# *********************************************************************************************************
# **** ABOVE: Rule parsing for pre-processing *** BELOW: Rule-2-Query building ************** 
# *********************************************************************************************************

from itertools import chain, combinations
def powerset(iterable):
	s = list(iterable)
	pwrset = list(chain.from_iterable(combinations(s, r) for r in range(len(s)+1)))
	pwrlist = []
	for x in pwrset:
		pwrlist.append(list(x))
	return pwrlist

def tok2query(tok, idx):
	itemcol = 'Item'+idx
	lemmcol = 'Lemma'+idx
	poscol = 'POS'+idx
	tokSize = len(tok)
	tokQuery = []
	
	itemMatch = []
	itemSkip = []
	lemmaMatch = []
	posMatch = []
	anyMatch = []

	for item in tok:
		if item.startswith('_LEMMA_#_'):
			lemmaMatch.append(item.replace('_LEMMA_#_',''))
		elif item.startswith('_POS_#_'):
			posMatch.append(item.replace('_POS_#_',''))
		elif item.startswith('!') and len(item) > 1 :
			itemSkip.append(item.replace('!',''))
		elif item == '_ANY_TOKEN_':
			anyMatch.append(item)	
		else:
			itemMatch.append(item)

	if len(itemMatch) > 0:
		inlist = "('"+"','".join(itemMatch)+"')"
		tokQuery.append(itemcol+' in '+inlist)
	if len(itemSkip) > 0:
		inlist = "('"+"','".join(itemSkip)+"')"
		tokQuery.append(itemcol+' not in '+inlist)
	if len(lemmaMatch) > 0:
		inlist = "('"+"','".join(lemmaMatch)+"')"
		tokQuery.append(lemmcol+' in '+inlist)
	if len(posMatch) > 0:
		inlist = "('"+"','".join(posMatch)+"')"
		tokQuery.append(poscol+' in '+inlist)
	if len(tokQuery) > 0:
		return ' and '.join(tokQuery)
	else:
		return ''

def rule2query(aruleDict):
	# format the token for querying n-gram dataset
	# n-gram header: N-GRAM Item1 Lemma1 POS1 ... Norm Good Random (3 last columns are scores)
	ruleQuery = []

	#print(ruleQuery)
	
	for key in aruleDict:
		index = str(key)
		ruletok = aruleDict[key]
		tokquery = tok2query(ruletok,index)
		if len(tokquery) > 0:
			ruleQuery.append(tokquery)
	if len(ruleQuery) == 1:
		ruleQueryStr = ruleQuery[0]
	elif len(ruleQuery) > 1:
		ruleQueryStr = ' and '.join(ruleQuery) # take the items and make a query string from it
	else:
		ruleQueryStr = ''
	return ruleQueryStr

def slidingWindow(w_size):
	seq = [1,2,3,4,5]
	seqList = []
	for i in range(len(seq) - w_size + 1):
		#print(seq[i: i + w_size])
		seqList.append(seq[i: i + w_size])
	return seqList

def nGramRange(seqList):
	minSize = len(seqList)
	lastElt = seqList[-1]
	upperGrams = []
	for i in range(lastElt, 6):
		upperGrams.append(i)
	return upperGrams

def rule2queryLR(ruleDict):
	resultQlist = []
	rSize = len(ruleDict)
	sequences = slidingWindow(rSize)
	
	for s in sequences:
		versDict = {}
		vcount = 0
		for key in ruleDict:
			versDict[s[vcount]] = ruleDict[key]
			vcount += 1
		versquery = rule2query(versDict)
		if versquery not in resultQlist and len(versquery) > 0:
			resultQlist.append((nGramRange(s),versquery))

	return resultQlist

def tok2queryMongo(tok, idx):
	itemcol = 'Item'+idx
	lemmcol = 'Lemma'+idx
	poscol = 'POS'+idx
	tokSize = len(tok)
	tokQuery = []

	tokQueryDict = {}
	
	itemMatch = []
	itemSkip = []
	lemmaMatch = []
	posMatch = []
	anyMatch = []

	for item in tok:
		if item.startswith('_LEMMA_#_'):
			lemmaMatch.append(item.replace('_LEMMA_#_',''))
		elif item.startswith('_POS_#_'):
			posMatch.append(item.replace('_POS_#_',''))
		elif item.startswith('!') and len(item) > 1 :
			itemSkip.append(item.replace('!',''))
		elif item == '_ANY_TOKEN_':
			anyMatch.append(item)	
		else:
			itemMatch.append(item)

	if len(itemMatch) > 0:
		tokQueryDict[itemcol] = {'$in':itemMatch}
	if len(itemSkip) > 0:
		tokQueryDict[itemcol] = {'$nin':itemSkip}
	if len(lemmaMatch) > 0:
		tokQueryDict[lemmcol] = {'$in':lemmaMatch}
	if len(posMatch) > 0:
		tokQueryDict[poscol] = {'$in':posMatch}
	
	return tokQueryDict


def rule2queryMongo(aruleDict):
	# format the token for querying n-gram dataset
	# n-gram header: N-GRAM Item1 Lemma1 POS1 ... Norm Good Random (3 last columns are scores)
	ruleQuery = []

	for key in aruleDict:
		index = str(key)
		ruletok = aruleDict[key]
		tokquery = tok2queryMongo(ruletok,index)
		if len(tokquery) > 0:
			ruleQuery.append(tokquery)

	if len(ruleQuery) == 1:
		return ruleQuery[0]
	
	elif len(ruleQuery) > 1:
		return {'$and':ruleQuery} # take the items and make a query string from it
	
	else:
		return {}

def rule2queryLRMongo(ruleDict):
	resultQlist = []
	rSize = len(ruleDict)
	sequences = slidingWindow(rSize)
	
	for s in sequences:
		versDict = {}
		vcount = 0
		for key in ruleDict:
			versDict[s[vcount]] = ruleDict[key]
			vcount += 1
		versquery = rule2queryMongo(versDict)
		if versquery not in resultQlist and len(versquery) > 0:
			resultQlist.append((nGramRange(s),versquery))

	return resultQlist

def queryBuilder(aRuleStr):
	queries = []
	parsedRuleDict = ruleParser(aRuleStr)
	tokCount = len(parsedRuleDict)
	optional = []
	for t in parsedRuleDict:
		if t.endswith('~'):
			optional.append(t)
	optionlist = powerset(optional)

	# build rule versions with optional items incl/excl combinations
	ruleVersions = []
	for option in optionlist:
		ruleVers = {}
		for key in parsedRuleDict:
			if key not in optional:
				ruleVers[key] = parsedRuleDict[key]
			elif key in option:
				ruleVers[key] = parsedRuleDict[key]
			else:
				pass
		ruleVersions.append(ruleVers)

	for r in ruleVersions:
		tcount = len(r) # tcount = n-gram to run Query on
		if tcount <= 5:
			results = rule2queryLR(r)
			# add this to the queries list as sublist or tuple with tcount
			for rslt in results:
				queries.append(rslt)

	return queries

def queryBuilderMongo(aRuleStr):
	queries = []
	parsedRuleDict = ruleParser(aRuleStr)
	tokCount = len(parsedRuleDict)
	optional = []
	for t in parsedRuleDict:
		if t.endswith('~'):
			optional.append(t)
	optionlist = powerset(optional)

	# build rule versions with optional items incl/excl combinations
	ruleVersions = []
	for option in optionlist:
		ruleVers = {}
		for key in parsedRuleDict:
			if key not in optional:
				ruleVers[key] = parsedRuleDict[key]
			elif key in option:
				ruleVers[key] = parsedRuleDict[key]
			else:
				pass
		ruleVersions.append(ruleVers)

	for r in ruleVersions:
		tcount = len(r) # tcount = n-gram to run Query on
		if tcount <= 5:
			results = rule2queryLRMongo(r)
			#print('\t--',results)
			# add this to the queries list as sublist or tuple with tcount
			for rslt in results:
				queries.append(rslt)
	return queries

'''
rule_sample = 'CT(provide) ( some ~ ) ( clear helpful complete useful important some ~ ) guidance ( on upon regarding concerning )'

results = queryBuilderMongo(rule_sample)
for r in results:
	ngrams = r[0]
	mongoQs = r[1]
	print(ngrams,'<---\t',mongoQs)
	print('--------------------------------------------------------')
'''