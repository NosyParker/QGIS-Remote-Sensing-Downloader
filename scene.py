import os
import logging
import requests
import json
from datetime import datetime
import subprocess
import calendar
import utils as utils
import config as config


logger = logging.getLogger(__name__)


class SatSceneError(Exception):
    pass


class Scene(object):

    _DEFAULT_SOURCE = 'aws_s3'

    def __init__(self, **kwargs):
        """ Инициируем объект-снимок с параметрами """
        self.metadata = kwargs
        required = ['scene_id', 'date', 'data_geometry', 'download_links']
        if not set(required).issubset(kwargs.keys()):
            raise SatSceneError('Невалидный снимок (требуемые параметры: %s' % ' '.join(required))
        self.filenames = {}
        # TODO - check validity of date and geometry, at least one download link

    def __repr__(self):
        return self.scene_id

    @property
    def scene_id(self):
        return self.metadata['scene_id']

    @property
    def platform(self):
        return self.metadata.get('satellite_name', '')

    @property
    def date(self):
        pattern = '%Y-%m-%d' if '-' in self.metadata['date'] else '%Y/%m/%d'
        return datetime.strptime(self.metadata['date'], pattern).date()

    @property
    def geometry(self):
        return self.metadata['data_geometry']

    @property
    def sources(self):
        return self.metadata['download_links'].keys()

    def links(self, source=_DEFAULT_SOURCE):
        """ Return dictionary of file key and download link """
        files = self.metadata['download_links'][source]
        prefix = os.path.commonprefix(files)
        keys = [os.path.splitext(f[len(prefix):])[0] for f in files]
        links = dict(zip(keys, files))
        if source == 'aws_s3' and 'aws_thumbnail' in self.metadata:
            links['thumb'] = self.metadata['aws_thumbnail']
        else:
            links['thumb'] = self.metadata['thumbnail']
        return links

    def geojson(self):
        """ Возвращает метаданные в формате GeoJSON """
        return {
            'type': 'Feature',
            'geometry': self.metadata['data_geometry'],
            'properties': self.metadata
        }

    def get_older_landsat_collection_links(self, link):
        """ Генерирует ссылки для устаревших версий """
        sid = os.path.basename(link).split('_')[0]
        return [link.replace(sid, sid[0:-1] + str(s)) for s in reversed(range(0, int(sid[-1]) + 1))]

    def download(self, key=None, source=_DEFAULT_SOURCE, path=None, subdirs=None):
        """ Download this key (e.g., a band, or metadata file) from the scene """
        links = self.links(source=source)
        # default to all files if no key provided
        if key is None:
            keys = links.keys()
        else:
            keys = [key]
        # loop through keys and get files
        for k in keys:
            if k in links:
                # work around because aws landsat not up to collection 1
                # so try to download older collection data if data not available
                if self.platform == 'landsat-8' and source == 'aws_s3':
                    link = self.get_older_landsat_collection_links(links[k])
                else:
                    link = [links[k]]
                for l in link:
                    try:
                        self.filenames[k] = self.download_file(l, path=path, subdirs=subdirs)
                        break
                    except Exception as e:
                        print(e)
                        pass
                if k in self.filenames:
                    #self.metadata['download_links'][source][k] = l
                    logger.info('Уже загружено %s в папку %s' % (l, self.filenames[k]))
                else:
                    logger.error('Не могу загрузить %s' % l)
        return self.filenames

    @classmethod
    def mkdirp(cls, path):
        """ Создавать директории рекурсивно """
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    def get_path(self, path=None, subdirs=None):
        """ Получает путь к текущей директории """
        if path is None:
            path = config.DATADIR
        if subdirs is None:
            subdirs = config.SUBDIRS

        # output path
        if subdirs != '':
            parts = subdirs.split('/')
            for p in parts:
                path = os.path.join(path, self.metadata[p])
        # make output path if it does not exist
        self.mkdirp(path)

        return path

    def download_file(self, url, path=None, subdirs=None, overwrite=False):
        """ Скачивает файл """
        
        path = self.get_path(path=path, subdirs=subdirs)
        #import pdb; pdb.set_trace()
        # if basename not provided use basename of url
        filename = os.path.join(path, os.path.basename(url))
        if os.path.exists(filename) and overwrite is False:
            return filename

        # download file
        logger.info('Скачивается с %s файл %s' % (url, filename))
        resp = requests.get(url, stream=True)
        if resp.status_code != 200:
            raise Exception("Не могу скачать данный файл - %s" % url)
        with open(filename, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        return filename

    def review_thumbnail(self):
        """ Display image and give user prompt to keep or discard """
        fname = self.download('thumb')['thumb']
        imgcat = os.getenv('IMGCAT', None)
        if imgcat is None:
            raise Exception("Set $IMGCAT to a terminal display program")
        cmd = '%s %s' % (imgcat, fname)
        print(cmd)
        os.system(cmd)
        print("Press Y to keep, N to delete, or any key to quit")
        while True:
            char = getch()
            if char.lower() == 'y':
                return True
            elif char.lower() == 'n':
                return False
            raise Exception('Cancel')


class Scenes(object):
    """ Коллекция объектов-Scene """

    def __init__(self, scenes):
        """ Инициируем объект со списком объектов-Scene """
        self.scenes = sorted(scenes, key=lambda s: s.date)

    def __len__(self):
        """ Число снимков """
        return len(self.scenes)

    def __getitem__(self, index):
        return self.scenes[index]

    def __setitem__(self, index, value):
        self.scenes[index] = value

    def __delitem__(self, index):
        self.scenes.delete(index)

    def dates(self):
        """ Получаем отсортированный список дат для всех снимков """
        return sorted([s.date for s in self.scenes])

    def sensors(self, date=None):
        """ List of all available sensors across scenes """
        if date is None:
            return list(set([s.platform for s in self.scenes]))
        else:
            return list(set([s.platform for s in self.scenes if s.date == date]))

    def print_scenes(self, params=[]):
        """ Print summary of all scenes """
        if len(params) == 0:
            params = ['date', 'scene_id']
        txt = 'Снимков (%s):\n' % len(self.scenes)
        txt += ''.join(['{:^20}'.format(p) for p in params]) + '\n'
        for s in self.scenes:
            txt += ''.join(['{:^20}'.format(s.metadata[p]) for p in params]) + '\n'
        print(txt)

    def text_calendar(self):
        """ Get calendar for dates """
        date_labels = {}
        for d in self.dates():
            sensors = self.sensors(d)
            if len(sensors) > 1:
                date_labels[d] = 'Multiple'
            else:
                date_labels[d] = sensors[0]
        return utils.get_text_calendar(date_labels)

    def save(self, filename, append=False):
        """ Save scene metadata """
        if append and os.path.exists(filename):
            with open(filename) as f:
                features = json.loads(f.read())['features']
        else:
            features = []
        geoj = self.geojson()
        geoj['features'] = features + geoj['features']
        with open(filename, 'w') as f:
            f.write(json.dumps(geoj))

    def geojson(self):
        """ Получить все метаданные в GEoJSON """
        features = [s.geojson() for s in self.scenes]
        return {
            'type': 'FeatureCollection',
            'features': features
        }

    @classmethod
    def load(cls, filename):
        """ Load a collections class from a GeoJSON file of metadata """
        with open(filename) as f:
            metadata = json.loads(f.read())['features']
        scenes = [Scene(**(md['properties'])) for md in metadata]
        return Scenes(scenes)

    def download(self, **kwargs):
        return [s.download(**kwargs) for s in self.scenes]

    def review_thumbnails(self):
        """ Review all thumbnails in scenes """
        new_scenes = []
        for scene in self.scenes:
            try:
                keep = scene.review_thumbnail()
                if keep:
                    new_scenes.append(scene)
            except Exception as e:
                return
        self.scenes = new_scenes


try:
    from msvcrt import getch
except ImportError:
    def getch():
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
