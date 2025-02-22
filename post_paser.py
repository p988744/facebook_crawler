import re
import json
import pandas as pd
from bs4 import BeautifulSoup
from utils import _extract_id, _get_headers, _init_request_vars
from requester import _get_homepage, _get_posts
from page_paser import _parse_entryPoint, _parse_identifier, _parse_docid
import datetime

def _parse_edgelist(resp):
    '''
    Take edges from the response by graphql api
    '''
    edges = []
    try:
        edges = resp.json()['data']['node']['timeline_feed_units']['edges']
    except:
        for data in resp.text.split('\r\n', -1):
            try:
                edges.append(json.loads(data)['data']['node']['timeline_list_feed_units']['edges'][0])
            except:
                edges.append(json.loads(data)['data'])
    return edges

def _parse_edge(edge):
    '''
    Parse edge to take informations, such as post name, id, message..., etc. 
    '''
    comet_sections = edge['node']['comet_sections']
    # name
    name = comet_sections['context_layout']['story']['comet_sections']['actor_photo']['story']['actors'][0]['name']
    
    # creation_time
    creation_time = comet_sections['context_layout']['story']['comet_sections']['metadata'][0]['story']['creation_time']
    
    # message
    try:
        message = comet_sections['content']['story']['comet_sections']['message']['story']['message']['text']
    except:
        message = comet_sections['content']['story']['comet_sections']['message_container']['story']['message']['text']
    
    # postid
    postid = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['subscription_target_id']
    
    # actorid
    pageid = comet_sections['context_layout']['story']['comet_sections']['actor_photo']['story']['actors'][0]['id']
    
    # comment_count
    comment_count = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['comment_count']['total_count']
    
    # reaction_count
    reaction_count = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['comet_ufi_summary_and_actions_renderer']['feedback']['reaction_count']['count']
    
    # share_count
    share_count = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['comet_ufi_summary_and_actions_renderer']['feedback']['share_count']['count']
    
    # toplevel_comment_count
    toplevel_comment_count = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['toplevel_comment_count']['count']
    
    # top_reactions
    top_reactions = comet_sections['feedback']['story']['feedback_context']['feedback_target_with_context']['ufi_renderer']['feedback']['comet_ufi_summary_and_actions_renderer']['feedback']['cannot_see_top_custom_reactions']['top_reactions']['edges']
    
    # comet_footer_renderer for link
    try:
        comet_footer_renderer = comet_sections['content']['story']['attachments'][0]['comet_footer_renderer']
        # attachment_title
        attachment_title = comet_footer_renderer['attachment']['title_with_entities']['text']
        # attachment_description
        attachment_description = comet_footer_renderer['attachment']['description']['text']
    except:
        attachment_title = ''
        attachment_description = ''
    
    # all_subattachments for photos
    try:
        try:
            media = comet_sections['content']['story']['attachments'][0]['styles']['attachment']['all_subattachments']['nodes']
            attachments_photos = ', '.join([image['media']['viewer_image']['uri'] for image in media])
        except:
            media = comet_sections['content']['story']['attachments'][0]['styles']['attachment']
            attachments_photos = media['media']['photo_image']['uri']
    except:
        attachments_photos = ''

    # cursor
    cursor = edge['cursor']
    
    # actor url
    actor_url = comet_sections['context_layout']['story']['comet_sections']['actor_photo']['story']['actors'][0]['url']
    
    # post url
    post_url = comet_sections['content']['story']['wwwURL']
    
    return [name, pageid, postid, creation_time, message, reaction_count, comment_count, toplevel_comment_count, share_count, top_reactions, attachment_title, attachment_description, attachments_photos, cursor, actor_url, post_url]

def _parse_domops(resp):
    '''
    Take name, data id, time , message and page link from domops
    '''
    data = re.sub(r'for \(;;\);','',resp.text)
    data = json.loads(data)
    domops = data['domops'][0][3]['__html']
    cursor = re.findall('timeline_cursor%22%3A%22(.*?)%22%2C%22timeline_section_cursor', domops)[0]
    content_list = []
    soup = BeautifulSoup(domops, 'lxml')
    
    for content in soup.findAll('div', {'class':'userContentWrapper'}):
        # name 
        name = content.find('img')['aria-label']
        # id
        dataid = content.find('div', {'data-testid':'story-subtitle'})['id']
        # actorid
        pageid = _extract_id(dataid, 0)
        # postid
        postid = _extract_id(dataid, 1)
        # time
        time = content.find('abbr')['data-utime']
        # message
        message = content.find('div', {'data-testid':'post_message'})
        if message == None:
            message = ''
        else:
            if len(message.findAll('p'))>=1:
                message = ''.join(p.text for p in message.findAll('p'))
            elif len(message.select('span > span'))>=2:
                message = message.find('span').text
        
        # attachment_title
        try:
            attachment_title = content.find('a', {'data-lynx-mode':'hover'})['aria-label']
        except:
            attachment_title = ''
        # attachment_description
        try:
            attachment_description = content.find('a', {'data-lynx-mode':'hover'}).text
        except:
            attachment_description = ''
        # actor_url   
        actor_url = content.find('a')['href'].split('?')[0]
        
        # post_url
        post_url = 'https://www.facebook.com/' + postid
        content_list.append([name, pageid, postid, time, message, attachment_title, attachment_description, cursor, actor_url, post_url])
    return content_list, cursor

def _parse_jsmods(resp):
    '''
    Take postid, pageid, comment count , reaction count, sharecount, reactions and display_comments_count from jsmods
    '''
    data = re.sub(r'for \(;;\);','',resp.text)
    data = json.loads(data)
    jsmods = data['jsmods']
    
    requires_list = []
    for requires in jsmods['pre_display_requires']:
        try:
            feedback = requires[3][1]['__bbox']['result']['data']['feedback']
            # subscription_target_id ==> postid
            subscription_target_id = feedback['subscription_target_id']
            # owning_profile_id ==> pageid
            owning_profile_id = feedback['owning_profile']['id']
            # comment_count
            comment_count = feedback['comment_count']['total_count']
            # reaction_count
            reaction_count = feedback['reaction_count']['count']
            # share_count
            share_count = feedback['share_count']['count']
            # top_reactions
            top_reactions =  feedback['top_reactions']['edges']
            # display_comments_count
            display_comments_count = feedback['display_comments_count']['count']
            
            # append data to list
            requires_list.append([subscription_target_id, owning_profile_id, comment_count, reaction_count, share_count, top_reactions, display_comments_count])
        except:
            pass

    # reactions--video posts
    for requires in jsmods['require']:
        try:
            # entidentifier ==> postid
            entidentifier = requires[3][2]['feedbacktarget']['entidentifier']
            # pageid
            actorid = requires[3][2]['feedbacktarget']['actorid']
            # comment count
            commentcount = requires[3][2]['feedbacktarget']['commentcount']
            # reaction count
            likecount = requires[3][2]['feedbacktarget']['likecount']
            # sharecount
            sharecount = requires[3][2]['feedbacktarget']['sharecount']
            # reactions
            reactions = []
            # display_comments_count
            commentcount = requires[3][2]['feedbacktarget']['commentcount']

             # append data to list
            requires_list.append([entidentifier, actorid, commentcount, likecount, sharecount, reactions, commentcount])
        except:
            pass
    return requires_list

def _parse_composite_graphql(resp):
    edges = _parse_edgelist(resp)
    df = []
    for edge in edges:
        try:
            ndf = _parse_edge(edge)
            df.append(ndf)
        except:
            pass
    df = pd.DataFrame(df, columns=['NAME', 'PAGEID', 'POSTID', 'TIME', 'MESSAGE', 'REACTIONCOUNT', 'COMMENTCOUNT', 'DISPLAYCOMMENTCOUNT', 
                                   'SHARECOUNT', 'REACTIONS', 'ATTACHMENT_TITLE', 'ATTACHMENT_DESCRIPTION', 'ATTACHMENT_PHOTOS', 'CURSOR', 'ACTOR_URL', 'POST_URL'])
    df = df[['NAME', 'PAGEID', 'POSTID', 'TIME', 'MESSAGE', 'ATTACHMENT_TITLE', 'ATTACHMENT_DESCRIPTION', 'ATTACHMENT_PHOTOS', 'REACTIONCOUNT',
             'COMMENTCOUNT', 'DISPLAYCOMMENTCOUNT', 'SHARECOUNT', 'REACTIONS', 'CURSOR', 'ACTOR_URL', 'POST_URL']]
    cursor =  df['CURSOR'].to_list()[-1]
    df['TIME'] = df['TIME'].apply(lambda x: datetime.datetime.fromtimestamp(int(x)).strftime("%Y-%m-%d %H:%M:%S"))
    max_date = df['TIME'].max()
    print('The maximum date of these posts is: {}, keep crawling...'.format(max_date))
    return df, max_date, cursor

def _parse_composite_nojs(resp):
    domops, cursor = _parse_domops(resp)
    domops = pd.DataFrame(domops, columns = ['NAME', 'PAGEID', 'POSTID', 'TIME', 'MESSAGE', 'ATTACHMENT_TITLE', 'ATTACHMENT_DESCRIPTION', 'CURSOR', 'ACTOR_URL', 'POST_URL'])
    domops['TIME'] = domops['TIME'].apply(lambda x: datetime.datetime.fromtimestamp(int(x)).strftime("%Y-%m-%d %H:%M:%S"))
    
    jsmods = _parse_jsmods(resp)
    jsmods = pd.DataFrame(jsmods, columns=['POSTID', 'PAGEID', 'COMMENTCOUNT', 'REACTIONCOUNT', 'SHARECOUNT', 'REACTIONS', 'DISPLAYCOMMENTCOUNT'])
    
    df = pd.merge(left=domops,
                  right=jsmods,
                  how='inner',
                  on=['PAGEID', 'POSTID'])

    df = df[['NAME', 'PAGEID', 'POSTID', 'TIME', 'MESSAGE', 'ATTACHMENT_TITLE', 'ATTACHMENT_DESCRIPTION', 
             'REACTIONCOUNT', 'COMMENTCOUNT', 'DISPLAYCOMMENTCOUNT', 'SHARECOUNT', 'REACTIONS', 'CURSOR',
             'ACTOR_URL', 'POST_URL']]
    max_date = df['TIME'].max()
    print('The maximum date of these posts is: {}, keep crawling...'.format(max_date))
    return df, max_date, cursor

if __name__ == '__main__':
    pageurl = 'https://www.facebook.com/mohw.gov.tw'
    pageurl = 'https://www.facebook.com/groups/pythontw'
    pageurl = 'https://www.facebook.com/Gooaye'
    pageurl = 'https://www.facebook.com/emily0806'
    pageurl = 'https://www.facebook.com/groups/pythontw'


    headers = _get_headers(pageurl)
    homepage_response = _get_homepage(pageurl, headers)
    entryPoint = _parse_entryPoint(homepage_response)
    identifier = _parse_identifier(entryPoint, homepage_response)
    docid = _parse_docid(entryPoint, homepage_response)
    df, cursor, max_date, break_times = _init_request_vars()

    resp = _get_posts(headers=headers, 
                    identifier=identifier, 
                    entryPoint=entryPoint,
                    docid=docid,
                    cursor=cursor)
    edges = _parse_edgelist(resp)
    len(edges)

    comet_sections = edges[2]['node']['comet_sections']

    for i, edge in enumerate(edges):
        try:
            _parse_edge(edge)
        except:
            print(i)

    pageurl = 'https://www.facebook.com/anuetw/'
    headers = _get_headers(pageurl)
    homepage_response = _get_homepage(pageurl=pageurl, headers=headers)
    entryPoint = _parse_entryPoint(homepage_response)
    identifier = _parse_identifier(entryPoint, homepage_response)
    docid = _parse_docid(entryPoint, homepage_response)
    df, cursor, max_date, break_times = _init_request_vars()

    resp = _get_posts(headers=headers, 
                    identifier=identifier, 
                    entryPoint=entryPoint,
                    docid=docid,
                    cursor=cursor)

    print(len(resp.text))
    content_list, cursor = _parse_domops(resp)
    _parse_jsmods(resp)[:1]



    headers = _get_headers(pageurl)
    homepage_response = _get_homepage(pageurl=pageurl, headers=headers)
    entryPoint = _parse_entryPoint(homepage_response)
    identifier = _parse_identifier(entryPoint, homepage_response)
    docid = _parse_docid(entryPoint, homepage_response)
    df, cursor, max_date, break_times = _init_request_vars()

    resp = _get_posts(headers=headers, 
                    identifier=identifier, 
                    entryPoint=entryPoint,
                    docid=docid,
                    cursor=cursor)
    # print(len(resp.text))
    df, max_date, cursor = _parse_composite_graphql(resp)
    print(max_date)
    print(cursor)
    df


    # pageurl = 'https://www.facebook.com/wealtholic/'
    # headers = _get_headers(pageurl)
    # homepage_response = _get_homepage(pageurl=pageurl, headers=headers)
    # entryPoint = _parse_entryPoint(homepage_response)
    # identifier = _parse_identifier(entryPoint, homepage_response)
    # docid = _parse_docid(entryPoint, homepage_response)
    # df, cursor, max_date, break_times = _init_request_vars()

    # resp = _get_posts(headers=headers, 
    #                   identifier=identifier, 
    #                   entryPoint=entryPoint,
    #                   docid=docid,
    #                   cursor=cursor)

    # df, max_date, cursor = _parse_composite_nojs(resp)
    # print(max_date)
    # print(cursor)
    # df