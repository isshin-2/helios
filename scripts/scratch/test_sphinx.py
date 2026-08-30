from pocketsphinx import Decoder
config = Decoder.default_config()
config.set_string('-keyphrase', 'stop')
config.set_float('-kws_threshold', 1e-20)
decoder = Decoder(config)
print("Decoder initialized")
