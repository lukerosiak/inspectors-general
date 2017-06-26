#!/usr/bin/env python

import datetime
import logging
import json

from utils import utils, inspector

"""
Not the GAO IG, but the GAO itself, who publishes an amazing number of
excellent reports:

* Reports
* Restricted (unreleased) reports
    http://www.gao.gov/restricted/restricted_reports

* Bid protest decisions, for which @vzvenyach wrote a Python scraper
    https://github.com/vzvenyach/gao
This is not included here but could be added in easily enough if it
is agreed that they are sufficiently "oversighty" to fit here.

* Open recommendations
    http://www.gao.gov/recommendations
I wrote a scraper for this but believe they are likely not be the best fit
for this repository, in part because we already have the reports the recs
come from and because they may eventually close. So it's not included here.

Report pages don't break out which agency they pertain to, if any, so this
lists GAO as both the inspector and the agency. However, they are mapped
internally, as they are browsable by agency here:
http://www.gao.gov/browse/agency/Executive

"""

# https://www.gao.gov

# options:
#   standard since/year options for a year range to fetch from.
#
# Notes for IG's web team:
# Not sure if the gao.gov/api/ interface is documented anywhere? Also,
# data-content_id that was used by an older Ruby scraper seems to have gone
# away.
# Without it the API is hit-or-miss because only one unpredictable version of
# the report--highlights, full report, etc,--gets the complete JSON response,
# while the others are missing URLs. Ideally you could pass a date range
# to the API and get an index.



def run(options):

  scrape_reports(options)
  #scrape_restricted_reports(options)


def scrape_reports(options):
  """Pull reports from "Reports and Testimonies - Browse by date" web page."""

  REPORTS_URL = 'http://www.gao.gov/browse/date/custom?adv_begin_date=01/01/' +\
    '%s&adv_end_date=12/31/%s&rows=50&o=%s' # % (year, year, offset)
  archive = 1950
  # Amazingly, reports go back to 1940, though those are unlikely to be
  # legible enough to OCR. Also very cool, even 1950s-era reports seem to have
  # a highlightable embedded text layer in them. Of course, it was the
  # General Accounting Office back then and less oversighty.

  year_range = inspector.year_range(options, archive)
  for year in year_range:
    is_next_page = True
    offset = 0
    while is_next_page:
      doc = utils.beautifulsoup_from_url(
        REPORTS_URL % (year, year, offset))
      results = doc.select("div.listing")
      for result in results:
        report = process_report(result, year_range)
        if report:
          inspector.save_report(report)
      page_links = doc.select("a.non-current_page")
      if len(page_links) and page_links[-1].text.startswith('Next'):
        offset += 50
      else:
        is_next_page = False


def process_report(result, year_range):

  """Use the report ID obtained from HTML to hit GAO's API"""

  # <img alt="pdf icon" src="/images/pdf.png"/> 
  # <a href="/assets/690/685452.pdf">View Report (PDF, 8 pages)</a>
  # 685452 is the ID used by the API.
  landing_url = 'https://www.gao.gov%s' % result.a['href']
  report_number = landing_url.split('/')[-1]

  pdf_links = result.findAll('li', {'class': 'pdf-link'})
  (pdf_url, highlights_url, accessible_url) = (None, None, None)
  for link in pdf_links:
    if 'View Report' in link.a.string:
      report_url = 'https://www.gao.gov%s' % link.a['href']
    if 'Highlights' in link.a.string:
      highlights_url = 'https://www.gao.gov%s' % link.a['href']
    if 'Accessible' in link.a.string:
      accessible_url = 'https://www.gao.gov%s' % link.a['href']
  # Last PDF is full report. First one could be Highlights.
  api_id = pdf_links[-1].a['href'].split('/')[-1].replace('.pdf', '')

  api_url = "http://www.gao.gov/api/id/%s" % api_id
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
  posted_at = details['actual_release_date'][:10]
  title = details['title']
  gao_type = details['document_type']
  description = ''
  if details.get('description', None):
    description = details['description']

  if int(published_on[:4]) not in year_range:
    logging.debug("[%s] Skipping, not in requested range." % report_url)
    return

  if not landing_url and not pdf_url:
    loggin.debug("[%s] No landing URL or PDF, skipping..." % report_id)
    return None

  report = {
    'inspector': 'gaoreports',
    'inspector_url': 'https://www.gao.gov',
    # often GAO reports do focus on a program in a specific external agency,
    # but we're not attempting to discern it in a structured way.
    # We'll just have GAO for the inspector and the agency.
    'agency': 'Government Accountability Office',
    'agency_name': 'Government Accountability Office',
    'report_id': report_number,
    'landing_url': landing_url,
    'url': report_url,
    'title': title,
    'type': details['document_type'], # report_type,
    'published_on': published_on,

    'accessible_url': accessible_url,
    'supplement_url': details['supplement_url'],
    'youtube_id': details['youtube_id'],
    'links': details['additional_links'],
    'description': description,
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
  archive = 2014

  year_range = inspector.year_range(options, archive)
  doc = utils.beautifulsoup_from_url(REPORTS_URL)
  results = doc.select("div.listing")
  for result in results:
    report = process_restricted_report(result, year_range)
    if report:
      inspector.save_report(report)

def process_restricted_report(div, year_range):
  """<div class="listing grayBorderTop" data-type="listing" >Information  Security: Federal Trade Commission Needs to Address Program Weaknesses<br />
                    <div class="release_info">
                    <span class=productNumberAndDate>GAO-15-76SU: Published: November 20, 2014</span>"""

  title = div.contents[0]
  span = div.div.span.string
  report_number = span.split(': ')[0]
  report_date_str = span.split(': ')[-1]
  report_date = datetime.datetime.strptime(report_date_str, "%B %d, %Y")

  if report_date.year not in year_range:
    return None

  report = {
    'inspector': 'gao',
    'inspector_url': 'https://www.gao.gov',
    # often GAO reports do focus on a program in a specific external agency,
    # but we're not attempting to discern it in a structured way.
    # We'll just have GAO for the inspector and the agency.
    'agency': 'Government Accountability Office',
    'agency_name': 'Government Accountability Office',
    'report_id': report_number,
    'unreleased': True,
    'landing_url': REPORTS_URL, # Just an index page, so don't harvest text from it.
    'title': title,
    'type': 'Unreleased report',
    'published_on': datetime.datetime.strftime(report_date, "%Y-%m-%d"),

  }

  return report








utils.run(run) if (__name__ == "__main__") else None
