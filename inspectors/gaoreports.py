#!/usr/bin/env python

import datetime
import logging
import os
from urllib.parse import urljoin

from utils import utils, inspector

"""
Not the GAO IG, but the GAO itself, who publishes an amazing number of
excellent reports:

* Reports, ported from Ruby:
    https://github.com/sunlightlabs/congress/blob/master/tasks/gao_reports/gao_reports.rb
* Restricted reports, which is a new dataset and worth including as unreleased reports
    http://www.gao.gov/restricted/restricted_reports
* Open recommendations
    http://www.gao.gov/recommendations
* Bid protest decisions, for which @vzvenyach wrote a Python scraper
    https://github.com/vzvenyach/gao

GAO provides an API for the first type. It also provides .txt versions
of those reports, called "Accessible Text".
"""

# <oig_url>
archive = 1997

# options:
#   standard since/year options for a year range to fetch from.
#
# Notes for IG's web team:
# Not sure if the gao.gov/api/ interface is documented anywhere?



def run(options):

  scrape_reports(options)
  #scrape_restricted_reports(options)
  #scrape_open_recs(options)
  #scrape_bid_protests(options)


def scrape_reports(options):
  """Pull reports from "Reports and Testimonies - Browse by date" web page."""

  REPORTS_URL = 'http://www.gao.gov/browse/date/custom?adv_begin_date=01/01/%s&adv_end_date=12/31/%s&rows=50&o=%s' # % (year, year, offset)

  year_range = inspector.year_range(options, archive)
  for year in year_range:
    is_next_page = True
    offset = 0
    while is_next_page:
      doc = utils.beautifulsoup_from_url(
        REPORTS_URL % (year, year, offset))
      results = doc.select("div.listing")
      for result in results:
        report = process_report(result)
        if report:
          inspector.save_report(report)
        page_links = doc.select("a.non-current_page")
        if len(page_links) and page_links[-1].text.startswith('Next'):
          offset += 50
        else:
          is_next_page = False


def process_report(result):

  """Use the report ID obtained from HTML to hit GAO's API"""

  report_id = result['data-content_id']

  api_url = "http://www.gao.gov/api/id/%s" % report_id
  details = json.loads(utils.download(api_url))[0]

  """looks like this {
    "youtube_id": null,
    "type": "reports",
    "content_id": "685451",
    "bucket_term": "Defense Management",
    "title": "DOD Has Taken Initial Steps to Formulate an Organizational Strategy, but These Efforts Are Not Complete",
    "description": null,
    "rptno": "GAO-17-523R",
    "docdate": "2017-06-23",
    "actual_release_date": "2017-06-23T12:00:00Z",
    "actual_release_date_formatted": "Jun 23, 2017",
    "original_release_dt": null,
    "category_img": "http://www.gao.gov/images/rip/defense.jpg",
    "category_img_alt": "defense icon, source: [West Covina, California] Progressive Management, 2008",
    "additional_links": "",
    "topics": [
    "National Defense"
    ],
    "subsite": [
    "Correspondence"
    ],
    "format": null,
    "mime_type_s": null,
    "ereport_flag": 0,
    "pdf_url": "http://www.gao.gov/assets/690/685452.pdf",
    "url": "http://www.gao.gov/products/GAO-17-523R",
    "document_type": "report",
    "supplement_url": null,
    "description_short": ""
    },"""

  # details directly from JSON
  categories = details.get('topics', [])
  if details['bucket_term']:
    categories.append(details['bucket_term'])
  published_on = details['docdate']
  posted_at = Time.parse details['actual_release_date']
  report_number = details['rptno']
  title = details['title']
  gao_type = details['document_type']
  description = ''
  if details.get('description', None):
    description = strip_tags(details['description'])

  if published_on.year not in year_range:
    logging.debug("[%s] Skipping, not in requested range." % report_url)
    return

  # urls
  landing_url = details['url']
  text_url = details['text_url']
  pdf_url = details['pdf_url']

  # seen a mixup - http://gao.gov/api/id/586393
  if pdf_url and pdf_url.endswith('.txt'):
    text_url = pdf_url
    pdf_url = None
    # seen it - http://gao.gov/api/id/586175
  elif pdf_url and not pdf_url.endswith('.pdf'):
    pdf_url = None

  if not landing_url and not pdf_url:
    loggin.debug("[%s] No landing URL or PDF, skipping..." % report_id)
    return None

  report = {
    'inspector': 'gao',
    'inspector_url': 'https://www.gao.gov',
    # often GAO reports do focus on a program in a specific external agency,
    # but we're not attempting to discern it in a structured way.
    # We'll just have GAO for the inspector and the agency.
    'agency': 'Government Accountability Office',
    'agency_name': 'Government Accountability Office'
    'report_id': report_number,
    'url': details['url'],
    'title': title,
    'type': details['document_type'], # report_type,
    'published_on': datetime.datetime.strftime(published_on, "%Y-%m-%d"),

    'text_url': details['text_url'],
    # if the text is downloaded, needs to be treated as ISO-8859-1 and then
    # converted to UTF-8. In Ruby:
    # full_text.force_encoding("ISO-8859-1")
    # full_text = full_text.encode "UTF-8", :invalid => :replace, :undef => :replace
    'pdf_url': details['pdf_url'],

    'supplement_url': details['supplement_url'],
    'youtube_id': details['youtube_id'],
    'links': details['additional_links'],
    'description': description
    'categories': categories,
    'category_img': details['category_img'],
    'category_img_alt': details['category_img_alt'],
    'subsite': details['subsite']

  }

  return report



def scrape_restricted_reports(options):
  """Restricted Products.

  A single HTML page lists unreleased reports since 2014, with no links."""

  # These reports are unreleased -- we could make this the text?
  TEXT = """The following products have been determined to contain either
classified information or controlled unclassified information by the audited
agencies and cannot be publicly released.

Members of Congress or congressional staff who wish to obtain one or more of
these products should call or e-mail the Congressional Relations Office.
All others who wish to obtain one or more of these products should follow the
instructions found on Requesting Restricted Products."""

  REPORTS_URL = 'http://www.gao.gov/restricted/restricted_reports'

  year_range = inspector.year_range(options, archive)
  doc = utils.beautifulsoup_from_url(REPORTS_URL)
  results = doc.select("div.listing")
  for result in results:
    report = process_restricted_report(result)
    if report:
      inspector.save_report(report)

def process_restricted_report(options):
  """<div class="listing grayBorderTop" data-type="listing" >Information  Security: Federal Trade Commission Needs to Address Program Weaknesses<br />
                    <div class="release_info">
                    <span class=productNumberAndDate>GAO-15-76SU: Published: November 20, 2014</span>"""

  report = {
    'inspector': 'gao',
    'inspector_url': 'https://www.gao.gov',
    # often GAO reports do focus on a program in a specific external agency,
    # but we're not attempting to discern it in a structured way.
    # We'll just have GAO for the inspector and the agency.
    'agency': 'Government Accountability Office',
    'agency_name': 'Government Accountability Office'
    'report_id': report_number,
    'unreleased': True,
    'landing_url': REPORTS_URL, # Just an index page, so don't harvest text from it.
    'title': title,
    'type': 'Unreleased report',
    'published_on': datetime.datetime.strftime(published_on, "%Y-%m-%d"),

  }

  return report



def scrape_open_recs(options):

  REPORTS_URL = 'https://www.gao.gov/recommendations?browse=orgdesc_s'
  doc = utils.beautifulsoup_from_url(REPORTS_URL)
  results = doc.select("div.listing")
  for result in results:
    report = process_restricted_report(result)
    if report:
      inspector.save_report(report)


topic_soup = BeautifulSoup(topics).findAll('a',{'class': 'facet_header'})

for a in topic_soup:
    topic_text = a.text
    topic_url = 'http://www.gao.gov/recommendations' + a['href'][1:]

    html = urllib2.urlopen(topic_url).read()

    getpage(topic_text, topic_url, html)

def getpage(topic_text, topic_url, html):

    soup = BeautifulSoup(html)

    rec_block = soup.findAll('div', {'class': 'recommendations_block'})
    reports = soup.findAll('div', {'class': 'ql_inner'})

    for i, r in enumerate(reports):
        report_link = r.a['href']
        report_title = r.a.text
        report_date = r.span.text
        year = report_date.split()[-1]

        recs = rec_block[i].findAll('div',{'class':'recommendations_individual_rec'})
        for rec in recs:
            s = str(rec).split('<br />')
            rec_text = s[0][
              len('<div class="recommendations_individual_rec"><b>Recommendation:</b>'):]
            rec_agency = s[2][len('<b>Agency:</b>'):]
            rec_status = s[3][len('<b>Status:</b>'):]
            rec_comments = s[5][len('<b>Comments:</b>'):]

            fout.writerow([topic_text, topic_url, rec_text, rec_agency, rec_status, rec_comments])

  report = {
    'inspector': 'gao',
    'inspector_url': 'https://www.gao.gov',
    # often GAO reports do focus on a program in a specific external agency,
    # but we're not attempting to discern it in a structured way.
    # We'll just have GAO for the inspector and the agency.
    'agency': 'Government Accountability Office',
    'agency_name': rec_agency,
    'report_id': report_number,
    'url': report_link,
    'title': report_title,
    'type': 'Open recommendation',
    'published_on': datetime.datetime.strftime(report_date, "%Y-%m-%d"),

  }




utils.run(run) if (__name__ == "__main__") else None
