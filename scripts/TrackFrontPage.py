import time
import datetime
import praw
import os
import pandas as pd
from pandas import Series, DataFrame
from scipy.stats.stats import pearsonr
from numpy import mean

r = praw.Reddit('Stats tracker by u/mechanicalreddit') # Change 'yourname' to your Reddit username

# Set the directories to save the data to
historical_data_directory="/home/pi/projects/RedditFresh/HistoricalData"
web_data_directory="/var/www/RedditFresh/data"

# Set the number of articles to get
num_arts = 50
num_new_arts = 200

i = 0
day = 1

# How often to update in minutes
update_time = 5

# How many times program will iterate in a day - 86400
times_in_day = float(86400)/(60*update_time)

# Number of historical correlations to keep
num_hist_data_points = 600

# Size of the correlation moving average window
ma_window = 3

while True:
    
    try:
        front_page = r.get_front_page(limit=num_arts)
        front_page_str=[str(x) for x in front_page]
    except:
        print "*****Something didn't work in getting front page articles*****"
    
    # Add a pause between requests as per reddit API rules
    time.sleep(10)
 
    try:
        newest_articles = r.get_new(limit=num_new_arts)
        newest_articles_str=[str(x).split('::')[1] for x in newest_articles]
    except:
        print "*****Something didn't work in getting newest articles*****"
    else:
        if 'old_newest_articles' in locals():
            # This may need to be a pd.concat
            total_new=list(set(old_newest_articles) | set(newest_articles_str))
            old_length = len(set(old_newest_articles))
            percent_new = ((len(total_new)-old_length)/float(old_length))*100
            old_newest_articles = newest_articles_str
        else:
            old_newest_articles = newest_articles_str
            
        
    temp_datetime=datetime.datetime.now()
    current_datetime=temp_datetime.strftime("%Y%m%d%H%M%S")
                    
    try:
        # This is painful, there has to be a better way
        front_page_series=Series(front_page_str, name="article").str.split('::').str.get(1)
        article_rank=Series(xrange(1, front_page_series.size+1), name=current_datetime)
        
    except:
        print "*****Something didn't work in converting the articles list to a series*****"
    else:
        if 'daily_data' in locals():
            tempDF=pd.concat([front_page_series, article_rank], axis=1)
            
            # This handles an issue that arises when the same article (or title)
            # is present more than once on any data pull
            tempDF=tempDF.drop_duplicates(cols="article")
            daily_data=daily_data.merge(tempDF, how="outer", on="article")
        else:
            daily_data=pd.concat([front_page_series, article_rank], axis=1)
            
            # This handles an issue that arises when the same article (or title)
            # is present more than once on any data pull
            daily_data=daily_data.drop_duplicates(cols="article")
        
        # Get the number of columns in the dataset
        ncols=daily_data.shape[1]        
         
        if (i >= 3):
                        
            # keep last two columns for correlations
            daily_data_small = daily_data.iloc[:, ncols-2:ncols] 
            
            # As a quick patch, fill missings with 51
            daily_data_small = daily_data_small.fillna(51)

            dds_col_names = daily_data_small.columns
            
            # Keep only cases where at least one value is <= 50
            temp_corr_data = daily_data_small[(daily_data_small[dds_col_names[0]]<=50) | (daily_data_small[dds_col_names[1]]<=50)]
            
            # Calculate a correlation between the new rom and the previously added row
            corr_val=pearsonr(temp_corr_data[dds_col_names[0]], temp_corr_data[dds_col_names[1]])
            
            # Calculate a root mean squared difference, i.e., a psuedo RMSE
            RMSD = (mean(((temp_corr_data[dds_col_names[0]] - temp_corr_data[dds_col_names[1]])**2)))**.5

            
            if 'corr_hist' in locals():
                ma_corrs.append(corr_val[0])
                del ma_corrs[0]
                corrMA = sum(ma_corrs)/len(ma_corrs)
                
                # if corr_hist already exists, use this
                temp_corr_hist = DataFrame({'datetime' : Series(current_datetime),
                               'correlation' : Series(corr_val[0]),
                                'significance' : Series(corr_val[1]), 
                                'percentnew' : Series(percent_new), 
                                'rmsd' : Series(RMSD),
                                'corrMA' : Series(corrMA)}, index=[0]) 
                corr_hist = corr_hist.append(temp_corr_hist)
                
                corr_hist = corr_hist.tail(num_hist_data_points)
                
            else:    
                # if corr hist doesn't already exist use this
                ma_corrs = [0] * ma_window
                corrMA = 0
                corr_hist = DataFrame({'datetime' : Series(current_datetime),
                                       'correlation' : Series(corr_val[0]),
                                        'significance' : Series(corr_val[1]), 
                                        'percentnew' : Series(percent_new), 
                                        'rmsd' : Series(RMSD),
                                       'corrMA' : Series(corrMA)},index=[0])  
        
        if not os.path.exists(historical_data_directory):
            os.makedirs(historical_data_directory)
			
        if not os.path.exists(web_data_directory):
            os.makedirs(web_data_directory)
        
        if (i > 0) & (i % (times_in_day) == 0):
            daily_data.to_csv(historical_data_directory + '/day_' + str(day) + '_daily_data.csv')
            daily_data = daily_data.iloc[150:,[0, ncols-times_in_day-1, ncols-1]] # Drop the oldest 150 articles to keep the datafile small. There is a better way to do this.
            corr_hist.to_csv(web_data_directory + '/corr_hist.csv')
            # print "Wrote **daily** data to file at " + current_datetime
            day+=1
            
        elif (i >= 0) & (i < 5):
            print "Warming up"
            
        elif (i > 5):
            corr_hist.to_csv(web_data_directory + '/corr_hist.csv')
            # print "Wrote **single iteration** data to file at " + current_datetime
        
        i+=1
            
    time.sleep(60*update_time)  
