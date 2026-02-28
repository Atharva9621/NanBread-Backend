def generate_report_from_comments(redditComments, youtubeComments):
    """
    input: conversations taken from redditIngestor, youtubeIngestor, googleIngestor etc.
    output: the json of report information to be sent to frontend 

    All the extracted comments from reddit/yt/google will be passed to llm and output wld be parsed
    to generate the detailed report.
    """
    return {}