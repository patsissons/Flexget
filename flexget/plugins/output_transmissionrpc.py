import os
from netrc import netrc, NetrcParseError
import logging
from flexget.plugin import *
from flexget import validator
log = logging.getLogger('transmissionrpc')


class PluginTransmissionrpc:
    """
      Add url from entry url to transmission
     
      Example: 
    
      transmissionrpc:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location
        debug: True

    Default values for the config elements:

    transmissionrpc:
        host: localhost
        port: 9091
        enabled: True
        debug: False
    """

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        advanced = root.accept('dict')
        advanced.accept('text', key='host')
        advanced.accept('number', key='port')
        """note that password is optional in transmission"""
        advanced.accept('file', key='netrc', required=False)
        advanced.accept('text', key='username', required=False)
        advanced.accept('text', key='password', required=False)
        advanced.accept('path', key='path', required=False)
        advanced.accept('boolean', key='addpaused', required=False)
        advanced.accept('number', key='maxconnections', required=False)
        advanced.accept('number', key='maxupspeed', required=False)
        advanced.accept('number', key='maxdownspeed', required=False)
        advanced.accept('decimal', key='ratio', required=False)
        advanced.accept('boolean', key='enabled')
        advanced.accept('boolean', key='debug')
        return root

    def get_config(self, feed):
        config = feed.config['transmissionrpc']
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('debug', False)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 9091)
        return config

    def on_process_start(self, feed):
        '''event handler'''
        set_plugin = get_plugin_by_name('set')

        set_plugin.instance.register_keys({'path': 'path', \
                                           'addpaused': 'boolean', \
                                           'maxconnections': 'number', \
                                           'maxupspeed': 'number',  \
                                           'maxdownspeed': 'number', \
                                           'ratio': 'decimal'})

    def on_feed_output(self, feed):
        """ event handler """
        config = self.get_config(feed)
        # don't add when learning
        if feed.manager.options.learn:
            return
        if not feed.accepted or not config['enabled']:
            return
        self.add_to_transmission(feed)

    def _make_torrent_options_dict(self, feed, entry):

        opt_dic = {}

        for opt_key in \
        ['path', 'addpaused', 'maxconnections', 'maxupspeed', 'maxdownspeed', 'ratio']:
            if opt_key in entry:
                opt_dic[opt_key] = entry[opt_key]
            elif opt_key in feed.config['transmissionrpc']:
                opt_dic[opt_key] = feed.config['transmissionrpc'][opt_key]

        options = {}
        options['add'] = {}
        options['change'] = {}

        if 'path' in opt_dic:
            options['add']['download_dir'] = os.path.expanduser(opt_dic['path'])
        if 'addpaused' in opt_dic and opt_dic['addpaused']: 
            options['add']['paused'] = True
        if 'maxconnections' in opt_dic:
            options['add']['peer_limit'] = opt_dic['maxconnections']

        if 'maxupspeed' in opt_dic:
            options['change']['uploadLimit'] = opt_dic['maxupspeed']
            options['change']['uploadLimited'] = True
        if 'maxdownspeed' in opt_dic:
            options['change']['downloadLimit'] = opt_dic['maxdownspeed']
            options['change']['downloadLimited'] = True

        if 'ratio' in opt_dic:
            options['change']['seedRatioLimit'] = opt_dic['ratio']
            if opt_dic['ratio'] == -1:
                '''
                seedRatioMode:
                0 follow the global settings
                1 override the global settings, seeding until a certain ratio
                2 override the global settings, seeding regardless of ratio
                '''
                options['change']['seedRatioMode'] = 2
            else:
                options['change']['seedRatioMode'] = 1

        return options

    def add_to_transmission(self, feed):
        """ adds accepted entries to transmission """
        conf = self.get_config(feed)
        try:
            import transmissionrpc
            from transmissionrpc.transmission import TransmissionError
        except:
            raise PluginError('Transmissionrpc module required.', log)
        if conf['debug']:
            log.setLevel(logging.DEBUG)

        user, password = None, None

        if 'netrc' in conf:

            try:
                user, account, password = netrc(conf['netrc']).authenticators(conf['host'])
            except IOError, e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError, e:
                log.error('netrc: %s, file: %s, line: %n' % (e.msg, e.filename, e.line))

        else:

            if 'username' in conf: 
                user = conf['username']
            if 'password' in conf: 
                password = conf['password']

        cli = transmissionrpc.Client(conf['host'], conf['port'], user, password)

        for entry in feed.accepted:
            if feed.manager.options.test:
                log.info('Would add %s to transmission' % entry['url'])
                continue
            options = self._make_torrent_options_dict(feed, entry)

            try:
                # TODO: Private trackers may need certain cookie headers, so
                # do something similar to what the deluge plugin does to
                # allow downloading the torrent file and adding using the
                # path to the downloaded file, or the "metainfo"
                # (base64-encoded .torrent content.
                r = cli.add(None, 30, filename=entry['url'], **options['add'])
            except TransmissionError, e:
                log.error(e.message)

            if len(options['change'].keys()) > 0:
                for id in r.keys():
                    cli.change(id, 30, **options['change'])

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
