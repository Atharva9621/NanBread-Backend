from core.ingestors.RedditIngestor import RedditIngestor
from core.ingestors.YoutubeIngestor import YoutubeIngestor
from core.chains.report_generation import generate_report_from_comments

def generate_report_from_user(user_id: str):
    # Step 1: fetch cmments from all ingestors for the given user_id

    reddit_commments = RedditIngestor().process(user_id)
    youtube_comments = YoutubeIngestor().process(user_id)
    
    # Step 2: pass the comments to llm and generate the report
    report = generate_report_from_comments(reddit_commments, youtube_comments)

    #Step 3: substitute the url values back in the report ( optional can just remove the whole substituttion thing if short on time )
    
    return report