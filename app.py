import streamlit as st
from st_clickable_images import clickable_images
import pandas as pd
import yt_dlp
import os
import requests 
from time import sleep

upload_endpoint = "https://api.assemblyai.com/v2/upload"
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"

headers = {
    #"authorization": st.secrets["auth_key"],
    "authorization":"3ad63fd3931342549f79971e5a36dce3",
    "content-type": "application/json"
    }

@st.cache_data
def save_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('title', None)
            save_location = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            if os.path.exists(save_location):
                #st.success(f"{video_title} has been successfully downloaded.")
                return video_title, save_location, info_dict.get('thumbnail', None)
            else:
                st.error("Download failed.")
                return None, None, None
    except yt_dlp.utils.DownloadError as e:
        st.error(f"Download error: {e}")
        return None, None, None
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None, None, None

@st.cache_data
def upload_to_AssemblyAI(save_location):
    CHUNK_SIZE = 5242880
    print(save_location)

    def read_file(filename):
        with open(filename, 'rb') as _file:
            while True:
                print("chunk uploaded")
                data = _file.read(CHUNK_SIZE)
                if not data:
                    break
                yield data

    upload_response = requests.post(
        upload_endpoint,
        headers=headers, data=read_file(save_location)
    )
    #print(upload_response.json())
    #st.write(upload_response.json())

    #if "error" in upload_response.json():
    #    return None, upload_response.json()["error"]

    audio_url = upload_response.json()['upload_url']
    print('Uploaded to', audio_url)

    return audio_url

@st.cache_data
def start_analysis(audio_url):
       
    ## Start transcription job of audio file
    data = {
        'audio_url': audio_url,
        'iab_categories': True,
        'content_safety': True,
        "summarization": True,
        "summary_model": "informative",
        "summary_type": "bullets"
    }

    transcript_response = requests.post(transcript_endpoint, json=data, headers=headers)
    if transcript_response.status_code != 200:
        st.error(f"transcript error: {transcript_response.json().get('error', 'Unknown error')}")
        return None, transcript_response.json().get('error', 'Unknown error')

    #print(transcript_response)
    #st.write(transcript_response.json())

    #if 'error' in transcript_response.json():
    #    return None, transcript_response.json()['error']

    transcript_id = transcript_response.json()['id']
    polling_endpoint = f"{transcript_endpoint}/{transcript_id}"

    return polling_endpoint

@st.cache_data
def sentiments_analysis(audio_url):
    ## Start sentiments_analysis job of audio file
    data = {
        "audio_url": audio_url,
        "sentiment_analysis": True
        }

    transcript_response = requests.post(transcript_endpoint, json=data, headers=headers)
    if transcript_response.status_code != 200:
        st.error(f"Sentiment analysis error: {transcript_response.json().get('error', 'Unknown error')}")
        return None, transcript_response.json().get('error', 'Unknown error')
    
    transcript_id = transcript_response.json()['id']
    sentiments = f"{transcript_endpoint}/{transcript_id}"

    #print(transcript_response)
    #st.write(transcript_response.json())

    return sentiments

@st.cache_data
def get_analysis_results(polling_endpoint):
        status = 'submitted'

        while True:
            print(status)
            polling_response = requests.get(polling_endpoint, headers=headers)
            status = polling_response.json()['status']

            if status == 'submitted' or status == 'processing' or status == 'queued':
                print('not ready yet')
                sleep(10)

            elif status == 'completed':
                print('creating transcript')

                return polling_response

                break
            else:
                print('error')
                return False
                break

st.title("YouTube Content Analyzer")
st.markdown("With this app, you can audit a YouTube channel to see if you'd like to sponsor them.")
st.markdown("1. A summary of the video.")
st.markdown("2. The topics that are discussed in the video.")
st.markdown("3. Whether there are any sensitive topics discussed in the video.")
st.markdown("Make sure your links are in the format: https://www.youtube.com/watch?v=HfNnuQOHAaw")

default_bool = st.checkbox("Use a default file")

if default_bool:
    file = open("./links.txt")
else:
    file = st.file_uploader("Upload a file that includes the links (.txt)")

if file is not None:
    dataframe = pd.read_csv(file, header=None)
    dataframe.columns = ['urls']
    urls_list = dataframe['urls'].tolist()

    titles = []
    locations = []
    thumbnails = []

    for video_url in urls_list:
        video_title, save_location, video_thumbnail = save_audio(video_url)
        if video_title and save_location and video_thumbnail:
            titles.append(video_title)
            locations.append(save_location)
            thumbnails.append(video_thumbnail)

    if thumbnails:
        selected_video = clickable_images(
            thumbnails, 
            titles=titles,
            div_style={"height": "200px", "display": "flex", "justify-content": "center", "flex-wrap": "wrap", "overflow-y": "auto"},
            img_style={"margin": "3px", "height": "100px"}
        )

    st.markdown(f"Thumbnail #{selected_video} clicked" if selected_video > -1 else "No image clicked")

    if selected_video > -1:
        video_url = urls_list[selected_video]
        video_title = titles[selected_video]
        save_location = locations[selected_video]

        st.header(video_title)
        st.audio(save_location)

        #upload mp3 file to AssemblyAI
        audio_url = upload_to_AssemblyAI(save_location) 

        #start analysis of the file 
        polling_endpoint = start_analysis(audio_url)

        #receive the results   
        results = get_analysis_results(polling_endpoint)

        #sentiment analysis
        sentiment_polling_endpoint = sentiments_analysis(audio_url)
        sentiment_results_response = get_analysis_results(sentiment_polling_endpoint)
        
        summary = results.json()['summary']
        topics = results.json()['iab_categories_result']['summary']
        sensitive_topics = results.json()['content_safety_labels']['summary']
        sentiment_results = sentiment_results_response.json()['sentiment_analysis_results']

        st.header("Summary of this video")
        st.write(summary)

        st.header("Sensitive content")
        if sensitive_topics != {}:
            st.subheader('🚨 Mention of the following sensitive topics detected.')
            moderation_df = pd.DataFrame(sensitive_topics.items())
            moderation_df.columns = ['topic','confidence']
            st.dataframe(moderation_df, use_container_width=True)
        else:
            st.subheader('✅ All clear! No sensitive content detected.')

        st.header("Topics discussed")
        topics_df = pd.DataFrame(topics.items())
        topics_df.columns = ['topic','confidence']
        topics_df["topic"] = topics_df["topic"].str.split(">")
        expanded_topics = topics_df.topic.apply(pd.Series).add_prefix('topic_level_')
        topics_df = topics_df.join(expanded_topics).drop('topic', axis=1).sort_values(['confidence'], ascending=False).fillna('')
        st.dataframe(topics_df)

        st.header("Sentiment Analysis Results")
        #st.write(sentiment_results)
        st.header("Topics Sentiment")
        topics_sentiments = pd.DataFrame(sentiment_results)
        topics_sentiments_df = topics_sentiments[['text', 'sentiment']]
        st.dataframe(topics_sentiments_df)

# Close the file if using the default file option
if default_bool and file is not None:
    file.close()