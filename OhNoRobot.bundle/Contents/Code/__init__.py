from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *

import string, re, operator, urlparse

from lxml import html

PLUGIN_PREFIX = '/video/ohnorobot'
PROVIDER_BASE = 'http://www.ohnorobot.com'
PROVIDER_INDEX = PROVIDER_BASE + '/series.pl'
ARCHIVE_HEAD = 'http://www.ohnorobot.com/archive.pl?comic='

DAY = 86400
CACHE_TIME = DAY

S_TITLE = 0
S_XPATH = 1
S_ENCODING = 2

knownSeries = dict()

####################################################################################################

def Start():
  global knownSeries
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L('Oh No Robot'), 'icon-default.png', 'art-default.png')
  
  Plugin.AddViewGroup('List', viewMode='List', mediaType='items')
  Plugin.AddViewGroup('Comic', viewMode='Coverflow', mediaType='items')
  
  MediaContainer.title1 = L('Oh No Robot')
  MediaContainer.viewGroup = 'List'
  MediaContainer.art = R('art-default.png')
  
  HTTP.SetCacheTime(CACHE_TIME)
  
  if not Data.Exists('series'):
    Data.SaveObject('series', knownSeries)
  else:
    knownSeries = Data.LoadObject('series')
  
####################################################################################################

def CreateDict():
  Dict.Set('pages', dict())
  
def UpdateCache():
  return

####################################################################################################

# TODO: add replace(_thumb) to url
# TODO: add None option to add comic images
# TODO: have add comic images auto-forward to next image
# TODO: handle relative img src

def MainMenu():
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(viewSeries, 'View Series')))
  dir.Append(Function(DirectoryItem(addSeries, 'Add Series')))
  return dir
  
def viewSeries(sender):
  global knownSeries
  dir = MediaContainer()
  for series in knownSeries.iterkeys():
    dir.Append(Function(DirectoryItem(IssuesMenu, title=series), key=knownSeries[series][S_TITLE]))
  return dir
  
def addSeries(sender):
  global knownSeries
  dir = MediaContainer(noCache=1)
  allSeries = getSeries(MediaContainer())
  for series in allSeries:
    seriesName = series.name
    Log(seriesName.encode('utf8'))
    if seriesName not in knownSeries:
      dir.Append(series)
  return dir

def getSeries(dir):
  seriesList = GetXML(PROVIDER_INDEX, True, encoding='iso-8859-1').xpath('//div[@id="centercontent"]/table/tr')
  dirList = list()
  for series in seriesList:
    name = series.xpath('child::td[1]/a')[0].text
    idLink = series.xpath('child::td[2]/a[1]')[0].get('href')
    id = re.sub(r'[^=]*=(\d+)', r'\1', idLink)
    dirList.append(Function(DirectoryItem(issuePages, title=name), key=id))
  dirListSorted = sorted(dirList, key=lambda x: x.name)
  for item in dirListSorted:
    dir.Append(item)
  return dir
  
####################################################################################################

def IssuesMenu(sender, key):
  global knownSeries
  pages = getIssues(MediaContainer(viewGroup='Comic'), key)
  seriesXPath = knownSeries[sender.itemTitle][S_XPATH]
  for page in pages:
    base = page._Function__kwargs['key']
    thumb = XML.ElementFromURL(base, True).xpath(seriesXPath)[0].get('src')
    thumb = urlparse.urljoin(base, thumb)
    Log(thumb)
    page.thumb = thumb
    #page.key = thumb.replace('_thumb','')
  return pages
  
def getIssues(dir, key):
  archivePageLinks = GetXML(ARCHIVE_HEAD + key, True, encoding='iso-8859-1').xpath('//body/p[4]/a')
  Log('Pages: ' + str(len(archivePageLinks)))
  archivePages = [ARCHIVE_HEAD + key, ]
  for link in archivePageLinks[0:-1]:
    archivePages.append(PROVIDER_BASE + link.get('href'))
  links = list()
  names = list()
  for archivePage in archivePages:
    for comic in GetXML(archivePage, True, encoding='iso-8859-1').xpath('//table/tr/td[1]/a'):
      name = comic.text
      link = comic.get('href')
      dir.Append(Function(DirectoryItem(noMenu, title=name), key=link))
  return dir

def noMenu(sender, key):
  pass
  
  
def uniqueImages(page1, page2, encoding):
  images2 = list()
  uniques = list()
  for image in GetXML(page2, True, encoding=encoding).xpath('//img'):
    images2.append(image.get('src'))
  for image in GetXML(page1, True, encoding=encoding).xpath('//img'):
    src = image.get('src')
    if src not in images2:
      uniques.append(src)
  return uniques
  
def getXPath(sender, key, page, seriesName, seriesID, encoding):
  global knownSeries
  image = GetXML(page, True, encoding=encoding).xpath('//img[@src="' + key + '"]')[0]
  Log('image source:' + key)
  xpath = getXPath2(image, '')
  Log('image path:' + xpath)
  Log(GetXML(page, True).xpath(xpath)[0].get('src'))
  
  knownSeries[seriesName] = [seriesID, xpath, encoding]
  Data.SaveObject('series', knownSeries)
  return
  
def getXPath2(key, childPath):
  parent = key.xpath('parent::*')
  name = key.xpath('name()')
  preSiblings = key.xpath('preceding-sibling::' + name)
  postSiblings = key.xpath('following-sibling::' + name)
  index = len(preSiblings) + 1 # 1-indexed
  if index == 1 and len(postSiblings) == 0:
    xpath = name
  else:
    xpath = name + '[' + str(index) + ']'
  if childPath != '':
    xpath = xpath + '/' + childPath
  if len(parent) != 0:
    return getXPath2(parent[0], xpath)
  else:
    return '/' + xpath
  
####################################################################################################

def issuePages(sender, key):
  allComics = getIssues(MediaContainer(), key)
  page1 = allComics[-1]._Function__kwargs['key']
  page2 = allComics[-2]._Function__kwargs['key']
  seriesName = sender.itemTitle
  dir = MediaContainer(title2=seriesName, nocache=1)
  encoding = GetEncoding(page1)
  Log('Encoding: ' + encoding)
  for image in uniqueImages(page1, page2, encoding):
    imageAbsolute = urlparse.urljoin(page1, image)
    dir.Append(Function(DirectoryItem(getXPath, thumb=imageAbsolute, title=imageAbsolute), key=image, page=page1, seriesName=seriesName, seriesID=key, encoding=encoding))
  return dir
  
  archivedPages = Dict.Get('pages')
  if key in archivedPages:
    dir = archivedPages[key]
  else:
    dir = MediaContainer()
    dir = grabPages(dir, key)
  dir.title2 = sender.itemTitle
  dir.viewGroup = 'Comic'
  return dir
  
def grabPages(dir, key):
  pages = GetXML(key, True).xpath('//div[@class="cpcal-day"]/a')
  for page in pages:
    dir.Append(grabPage(page))
  return dir
  
def grabPage(page):
  image = GetXML(page.get('href'), True).xpath('//div[@id="comic"]/img')[0]
  title = image.get('title')
  thumb = image.get('src')
  url = thumb.replace('_thumb','')
  return PhotoItem(url, thumb=thumb, title=title)

####################################################################################################
  
def GetXML(theUrl, use_html_parser=True, encoding="utf8"):
  return XML.ElementFromString(HTTP.Request(url=theUrl, cacheTime=CACHE_TIME, encoding=encoding), use_html_parser)
  
def GetEncoding(url):
  return GetXML('http://validator.w3.org/check?uri=' + String.Quote(url) + '&charset=%28detect+automatically%29&doctype=Inline&group=0').xpath('//table[@class="header"]/tr[3]/td[1]')[0].text
####################################################################################################
