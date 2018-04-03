import os
import sys
import json
import logging
from .version import __version__
from search import Search
from scene import Scenes
from parser import SatUtilsParser


logger = logging.getLogger(__name__)
logging.getLogger('requests').setLevel(logging.CRITICAL)


def main(review=False, printsearch=False, printmd=None, printcal=False,
         load=None, save=None, append=False, download=None, source='aws_s3', **kwargs):
    """ Главная функция для осуществления всего поиска/загрузки """

    if load is None:
        if printsearch:
            txt = 'Искать снимки, удовлетворяющие критериям:\n'
            for kw in kwargs:
                if kw == 'intersects':
                    geom = json.dumps(json.loads(kwargs[kw])['geometry'])
                    txt += ('{:>20}: {:<40} ...\n'.format(kw, geom[0:70]))
                else:
                    txt += ('{:>20}: {:<40}\n'.format(kw, kwargs[kw]))
            print(txt)

        # get scenes from search
        search = Search(**kwargs)
        scenes = Scenes(search.scenes())
    else:
        scenes = Scenes.load(load)

    if review:
        if not os.getenv('IMGCAT', None):
            raise ValueError('Set IMGCAT envvar to terminal image display program to use review feature')
        scenes.review_thumbnails()

    # print summary
    if printmd is not None:
        scenes.print_scenes(printmd)

    # print calendar
    if printcal:
        print(scenes.text_calendar())

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save, append=append)

    print('%s снимков найдено' % len(scenes))

    # download files given keys
    if download is not None:
        for key in download:
            scenes.download(key=key, source=source)

    return scenes


def cli():
    parser = SatUtilsParser(description='sat-search (v%s)' % __version__)
    args = parser.parse_args(sys.argv[1:])

    # read the GeoJSON file
    if 'intersects' in args:
        if os.path.exists(args['intersects']):
            with open(args['intersects']) as f:
                args['intersects'] = json.dumps(json.loads(f.read()))

    # enable logging
    logging.basicConfig(stream=sys.stdout, level=args.pop('verbosity') * 10)

    scenes = main(**args)
    return len(scenes)


if __name__ == "__main__":
    cli()
