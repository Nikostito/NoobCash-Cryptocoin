# import block
from wallet import Wallet
import requests


class Register:
    def __init__(self, node_id, address):
        self.wallet = Wallet(node_id)
        self.wallet.create_keys()
        self.wallet.save_keys()
        self.address = address
        self.public_key = self.wallet.public_key
        self.private_key = self.wallet.private_key
        self.id = -1 #Will be set automatically with bootstrap node's cache!
        self.ring = []

    '''
    Add this node to the ring, only the bootstrap node can add a node to the
    ring after checking his wallet and ip:port address
    bottstrap node informs all other nodes and gives the request node an id
    and 100 NBCs
    '''
    def register_node_to_ring(self, node):
        # node is {address: , public_key}
        self.ring.append({
            'address': node['address'],
            'public_key': node['public_key'],
            'id': node['id']
        })

    '''
    The Bootstrapper Node will POST every other node and inform it about
    the final ring with all the connected nodes
    '''
    def broadcast_ring(self):
        for node in self.ring:
            if node['address'] != self.address:
                addr = 'http://' + node['address'] + '/connect'
                requests.post(addr, json=self.ring)
