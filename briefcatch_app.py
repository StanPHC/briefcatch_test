import streamlit as st
import pandas as pd
import os

from io import BytesIO
import base64
# from pyxlsb import open_workbook as open_xlsb
import zipfile
from datetime import datetime

from pymongo import MongoClient

from ruleParser import *

st.set_page_config(page_title='N-Gram Lookup', page_icon=':briefcase:')

# ==================================================================
# LOADING THE NGRAMS
# ==================================================================

@st.cache(allow_output_mutation=True, suppress_st_warning=True)
def connect2db():
	try:
		client = MongoClient("mongodb+srv://admin:AsctKNuRYDNvYIKm@cluster0.sn8m5.mongodb.net/?retryWrites=true&w=majority")
		db = client.briefcatch
		return db
	except:
		return None

mongo_db = connect2db()


# ====================================================================
# FUNCTIONALITY
# ====================================================================


def df_to_excel(mydf, rankOption):
	output = BytesIO()
	writer = pd.ExcelWriter(output, engine='xlsxwriter')
	mydf['Norm'] = pd.to_numeric(mydf['Norm'], downcast='float')
	mydf['Good'] = pd.to_numeric(mydf['Good'], downcast='float')
	mydf['Random'] = pd.to_numeric(mydf['Random'], downcast='float')
	mydf['Gd-Rnd-Ratio'] = pd.to_numeric(mydf['Gd-Rnd-Ratio'], downcast='float')
	mydf_ranked = mydf.sort_values(by=['Rule ID',rankOption], ascending=[True,False])
	mydf_ranked.to_excel(writer,index=False,sheet_name='Results')
	workbook  = writer.book
	worksheet = writer.sheets['Results']
	scoreformat = workbook.add_format({'num_format':'0.0000'})
	start_col_idx = mydf_ranked.columns.get_loc('Norm')
	end_col_idx = mydf_ranked.columns.get_loc('Gd-Rnd-Ratio')
	worksheet.set_column(start_col_idx,end_col_idx,None,scoreformat)
	writer.save()
	processed_data = output.getvalue()
	return processed_data

def generateResultsAll(inputRuleDict):
	outputResults = []
	for r in inputRuleDict:

		ruleID = r
		ruleLst = inputRuleDict[r]
		ruleDF0 = pd.DataFrame({'Rule / Pattern': ruleLst[0], 'Correction / Recommendation': ruleLst[1], 'Rule ID': [ruleID]})
		searchTxt = ruleLst[0]

		resultDFs = {}
			
		try: # WRAP IN TRY CATCH STATEMENT, SIGNAL RULE ID IF Failed 
			resultQs = queryBuilderMongo(searchTxt)
			for rq in resultQs:
				gramsInt = rq[0]
				queryStr = rq[1]

				for g in gramsInt:
					collecName = 'ngrams_' + str(g)
					hits = mongo_db[collecName].find(queryStr)
					mqResults = list(hits)
					if len(mqResults) > 0:

						df_selection = pd.DataFrame.from_dict(mqResults,orient='columns').drop(columns=['_id'])

						if not df_selection.empty:
							if g not in resultDFs:
								resultDFs[g] = df_selection #.sort_values(rankOption,ascending=False)
							else:
								oldDF = resultDFs[g]
								resultDFs[g] = pd.concat([oldDF,df_selection], ignore_index=True) #.sort_values(rankOption,ascending=False)
		except:
			st.warning('Failed to process Rule ID# ' + str(ruleID))
		
		if len(resultDFs) > 0:
			# Add n-size column to each results table
			concatlist = []
			for g in resultDFs:
				resultDFs[g].insert(0,'N-size',str(g)+'-gram')
				concatlist.append(resultDFs[g])
			# concatenate results
			masterResultDF = pd.concat(concatlist)
			
			# add rule information columns in positions 0 and 1
			masterResultDF.insert(0,'Rule / Pattern',ruleLst[0])
			masterResultDF.insert(1,'Correction / Recommendation',ruleLst[1])
			masterResultDF.insert(2,'Rule ID',ruleID)
			outputResults.append(masterResultDF) #.sort_values(rankOption,ascending=False))
			
	if len(outputResults) > 0:
		outputDF = pd.concat(outputResults)
		# shift the score columns to the end
		outputDF.insert(len(outputDF.columns)-1, 'Norm', outputDF.pop('Norm'))
		#outputDF.insert(len(outputDF.columns)-1, 'Scotus', outputDF.pop('Scotus'))
		outputDF.insert(len(outputDF.columns)-1, 'Good', outputDF.pop('Good'))
		outputDF.insert(len(outputDF.columns)-1, 'Random', outputDF.pop('Random'))
		outputDF.insert(len(outputDF.columns)-1, 'Gd-Rnd-Ratio', outputDF.pop('Gd-Rnd-Ratio'))

		return outputDF
	else:
		return pd.DataFrame()


def clear_resultsdir():
	dirpath = os.path.join(os.getcwd(),'results')
	for filename in os.listdir(dirpath):
		fpath = os.path.join(dirpath,filename)
		try:
			os.unlink(fpath)
		except Exception as e:
			print('Failed to delete %s. Exception: %s' % (fpath, e))

def runSubmit():
	clear_resultsdir()
	inRuleDict = {}
	resultFiles = {}
	if st.session_state['rule_file'] is None:
		st.warning('Please upload a valid rules file .xlsx')
	else:
		dfinrules=(pd.read_excel(load_file)).dropna(how='all')
		for index, row in dfinrules.iterrows():
			row_id = str(int(row['Rule ID']))
			row_rule = row['Rule / Pattern']
			if 'Correction / Recommendation' in dfinrules:
				row_correction = row['Correction / Recommendation']
			else:
				row_correction = ''
			inRuleDict[row_id] = [row_rule, row_correction]
		
		results_df = generateResultsAll(inRuleDict)
		st.success('Processing complete!')
		timestampStr = datetime.now().strftime("%Y%m%d_%H%M%S")
		if len(results_df.index) == 0:
			st.warning('No viable results!')
		else:
			df_xlsx_binary = df_to_excel(results_df,rank_option)
			st.download_button('Download Results', data=df_xlsx_binary,file_name='results_'+timestampStr+'.xlsx')

# =====================================================================
# USER INTERFACE
# =====================================================================

st.header('N-Gram Lookup :briefcase: :scales: :sparkles:')
#st.markdown('---')

st.write('Upload Excel file containing at least one rule to analyze. The Excel table must include at least the following column names:  \n[[Rule / Pattern]] and [[Rule ID]] to proceed.')

load_file = st.file_uploader(label="",key='rule_file',accept_multiple_files=False, type=['.xlsx','.xls'])

rank_option = st.selectbox('Rank results per score by:',('Norm', 'Good', 'Random','Gd-Rnd-Ratio'),key='rank_by')
submit = st.button('SUBMIT',key='submit_btn')
st.markdown('---')

if submit:
	runSubmit()