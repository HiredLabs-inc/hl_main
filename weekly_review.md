# Architecturally there is currently 1 concern: CURRENT PHASE
# current phase: retrieving from db and processing from db, and can work from it with current sets, playing with different sets, selectively grabbing certain categories of keywords
# REFACTOR .json out so that data is being accessed from db after job description is added and analysis done
# have to access db through views.py “class JobDetailView” line 341
# retrieve out of db instead of json
# then pass into “analyze” function in keyword_analyzer.py in a way that it can be one or more categories (nltk_stopwords, low_value, industry_protected)
# testing plan– test out how stopword categories are working, integration, functionality; make different tweaks to play with stopword parameters; make sure code can do as intended; DOCUMENT: what tests i did; why i did it; how; results; one test is an algorithm test- known input and an expected output