import traceback
import re

from bs4 import BeautifulSoup
from couchpotato import fireEvent
from couchpotato.core.helpers.rss import RSS
from couchpotato.core.helpers.variable import getImdb, splitString, tryInt

from couchpotato.core.logger import CPLog
from couchpotato.core.providers.automation.base import Automation

from couchpotato.core.providers.base import MultiProvider


log = CPLog(__name__)


class IMDB(MultiProvider):

    def getTypes(self):
        return [IMDBWatchlist, IMDBAutomation]


class IMDBBase(Automation, RSS):

    interval = 1800

    def getInfo(self, imdb_id):
        return fireEvent('movie.info', identifier = imdb_id, extended = False, merge = True)


class IMDBWatchlist(IMDBBase):

    enabled_option = 'automation_enabled'

    def getIMDBids(self):

        movies = []

        watchlist_enablers = [tryInt(x) for x in splitString(self.conf('automation_urls_use'))]
        watchlist_urls = splitString(self.conf('automation_urls'))

        index = -1
        for watchlist_url in watchlist_urls:

            try:
                # Get list ID
                ids = re.findall('(?:list/|list_id=)([a-zA-Z0-9\-_]{11})', watchlist_url)
                if len(ids) == 1:
                    watchlist_url = 'http://www.imdb.com/list/%s/?view=compact&sort=created:asc' % ids[0]
                # Try find user id with watchlist
                else:
                    userids = re.findall('(ur\d{7,9})', watchlist_url)
                    if len(userids) == 1:
                        watchlist_url = 'http://www.imdb.com/user/%s/watchlist?view=compact&sort=created:asc' % userids[0]
            except:
                log.error('Failed getting id from watchlist: %s', traceback.format_exc())

            index += 1
            if not watchlist_enablers[index]:
                continue

            start = 0
            while True:
                try:

                    w_url = '%s&start=%s' % (watchlist_url, start)
                    log.debug('Started IMDB watchlists: %s', w_url)
                    html = self.getHTMLData(w_url)

                    try:
                        split = splitString(html, split_on="<div class=\"list compact\">")[1]
                        html = splitString(split, split_on="<div class=\"pages\">")[0]
                    except:
                        pass

                    imdbs = getImdb(html, multiple = True) if html else []

                    for imdb in imdbs:
                        if imdb not in movies:
                            movies.append(imdb)

                        if self.shuttingDown():
                            break

                    log.debug('Found %s movies on %s', (len(imdbs), w_url))

                    if len(imdbs) < 250:
                        break

                    start += 250

                except:
                    log.error('Failed loading IMDB watchlist: %s %s', (watchlist_url, traceback.format_exc()))

        return movies


class IMDBAutomation(IMDBBase):

    enabled_option = 'automation_providers_enabled'

    chart_urls = {
        'theater': 'http://www.imdb.com/movies-in-theaters/',
        'top250': 'http://www.imdb.com/chart/top',
        'boxoffice': 'http://www.imdb.com/chart/',
    }

    first_table = ['boxoffice']

    def getIMDBids(self):

        movies = []

        for url in self.chart_urls:
            if self.conf('automation_charts_%s' % url):
                data = self.getHTMLData(self.chart_urls[url])
                if data:
                    html = BeautifulSoup(data)

                    try:
                        result_div = html.find('div', attrs = {'id': 'main'})

                        try:
                            if url in self.first_table:
                                table = result_div.find('table')
                                result_div = table if table else result_div
                        except:
                            pass

                        imdb_ids = getImdb(str(result_div), multiple = True)

                        for imdb_id in imdb_ids:
                            info = self.getInfo(imdb_id)
                            if info and self.isMinimalMovie(info):
                                movies.append(imdb_id)

                            if self.shuttingDown():
                                break

                    except:
                        log.error('Failed loading IMDB chart results from %s: %s', (url, traceback.format_exc()))

        return movies
