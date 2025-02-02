import json
from datetime import datetime
import os
import tweepy as twp
import re
from ibm_watson import ToneAnalyzerV3
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
import mysql.connector
import urllib.parse
import time


def prolyzer(event, context):
    print("")
    search_term = event["queryStringParameters"]['search']
    user = event["queryStringParameters"]['user']

    consumer_key = 'k7bmKlFjUf3eyFcwpqi1D34aZ'
    consumer_secret = 'l4u0IRz5AYt9HXThR5lWTN41dTX5UMrs3VmZnmNPZky1mJmf7M'
    access_token = '1263822842-QDqzja2ZGdE2RWlL12UxEnMCcGsDUxDkxsfdDZc'
    access_token_secret = 'gcRxVFfwpeQr8mGF4BLP9ScK2qJnxWZxnneoq0fQFDznq'

    auth = twp.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = twp.API(auth)

    authenticator = IAMAuthenticator('G7Um77PYTSWaI23-QJg-NqJrDrECeUnzn1_nSCbPkS-Q')
    tone_analyzer = ToneAnalyzerV3(
        version='2017-09-21',
        authenticator=authenticator
    )

    tone_analyzer.set_service_url(
        'https://api.us-south.tone-analyzer.watson.cloud.ibm.com/instances/046af756-8b3b-4b48-be22-627b30bf6321')

    tone_analyzer.set_disable_ssl_verification(True)

    print("Connecting to database...")
    mydb = mysql.connector.connect(
        host=os.environ.get("DB_ENDPOINT"),
        user="admin",
        passwd="password",
        database=os.environ.get("TABLE_NAME")
    )
    print("Connected to database")

    mycursor = mydb.cursor()
    
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    search_words = search_term

    total_tweets = ''
    # Collect tweets
    print("Collecting 100 tweets for search term " + search_term)
    tweets = twp.Cursor(api.search, q=search_words, lang="en",tweet_mode='extended').items(100)

    for tweet in tweets:
        total_tweets = total_tweets + ' '.join(
            re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t]) |(\w+:\/\/\S+)", " ", tweet.full_text).split())
        latitude = ''
        longtitude = ''
        if tweet.geo:
            latitude = tweet.geo.get('coordinates')[0]
            longtitude = tweet.geo.get('coordinates')[1]
        hashtags = tweet.entities['hashtags']
        thashtag = ''
        for hashtag in hashtags:   
            thashtag = thashtag + hashtag['text'] + ","
        if thashtag.endswith(","):
            thashtag = thashtag[:-1]
        #print(thashtag)
        sql = "INSERT INTO tweets (search_term,full_text,lat,lon,userlocation,hashtags,created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (search_words,tweet.full_text,latitude,longtitude,tweet.user.location,thashtag,now)
        mycursor.execute(sql, val)

    print(total_tweets)
    tone_analysis = tone_analyzer.tone(
        {'text': total_tweets},
        content_type='application/json'
    ).get_result()
    
    document_tones = tone_analysis.get('document_tone')
    
    score1 = ""
    toneid1 = ""
    tonename1 = ""
    score2 = ""
    toneid2 = ""
    tonename2 = ""
    for value in document_tones.values():
        score1 = value[0].get('score')
        toneid1 = value[0].get('tone_id')
        tonename1 = value[0].get('tone_name')
        try:
            score2 = value[1].get('score')
            toneid2 = value[1].get('tone_id')
            tonename2 = value[1].get('tone_name')
        except IndexError:
            score2 = 'null'
            toneid2 = 'null'
            tonename2 = 'null'

    print("Inserting into database")
    sql1 = "INSERT INTO resultsdump (search_term,tweetsdump,resultsdump,created_at) VALUES (%s, %s, %s, %s)"
    val1 = (search_words,str(total_tweets),str(tone_analysis),now)
    mycursor.execute(sql1, val1)

    sql2 = "INSERT INTO results (search_term,score1,toneid1,tonename1,score2,toneid2,tonename2,user,created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    val2 = (search_words,score1,toneid1,tonename1,score2,toneid2,tonename2,user,now)
    mycursor.execute(sql2, val2)
    
    data = {}
    data['search_term'] = search_words
    data['score1'] = score1
    data['toneid1'] = toneid1
    data['tonename1'] = tonename1
    data['score2'] = score2
    data['toneid2'] = toneid2
    data['tonename2'] = tonename2
    data['user'] = user
    data['created_at'] = now

    mydb.commit()
    mycursor.close()
    print("Closing connection to database")
    mydb.close()
    print("Connection to database closed")

    response = {
        "statusCode": 200,
        "body": json.dumps({
            "tone_response": data
        }),
        "headers": {
            "Access-Control-Allow-Origin": '*',
            "Access-Control-Allow-Credentials": True,
        }
    }

    return response


handler = prolyzer