from flask import Flask, jsonify, request, send_from_directory, render_template
import sys
import requests
from flask_cors import CORS
from register import Register
from wallet import Wallet
from werkzeug.contrib.cache import SimpleCache
from blockchain import Blockchain

app = Flask(__name__)
CORS(app)
cache = SimpleCache()

@app.route('/', methods=['GET'])
def get_node_ui():
    return send_from_directory('ui', 'node.html')


@app.route('/register', methods=['POST'])
def post_node():
    counter = cache.get('counter')
    node = cache.get('node')
    data = request.get_json()
    # Add the new node to the bootstrapper's ring and update the counters
    data['id'] = counter
    register.register_node_to_ring(data)

    cache.set('node', node)
    cache.set('counter', counter + 1)

    return jsonify('Bootstrap notified successfully'), 200

@app.route('/connect', methods=['POST'])
def post_connect():
    ring = request.get_json()
    node = cache.get('node')

    for nd in ring:
        if nd['address'] == register.address:
            register.id = nd['id']
            cache.set('node', node)
    return jsonify('OK'), 200

@app.route('/broadcast-ring')
def get_broadcast_ring():
    node = cache.get('node')
    register.broadcast_ring()
    return jsonify('Broadcasted the ring successfully'), 200


@app.route('/network', methods=['GET'])
def get_network_ui():
    return send_from_directory('ui', 'network.html')


@app.route('/wallet', methods=['POST'])
def create_keys():
    global blockchain
    if is_bootstrap:
        response = {
            'public_key': register.public_key,
            'private_key': register.private_key,
            'funds': blockchain.get_balance()
        }
        return jsonify(response), 201

    else:
        register.wallet.create_keys()
        if register.wallet.save_keys():
            blockchain = Blockchain(register.public_key, register.private_key, node_id, nodes_number)
            response = {
                'public_key': register.public_key,
                'private_key': register.private_key,
                'funds': blockchain.get_balance()
            }
            return jsonify(response), 201
        else:
            response = {
                'message': 'Saving the keys failed.'
            }
            return jsonify(response), 500


@app.route('/wallet', methods=['GET'])
def load_keys():
    if register.wallet.load_keys():
        global blockchain
        blockchain = Blockchain(register.public_key, register.private_key, node_id, nodes_number)
        response = {
            'public_key': register.public_key,
            'private_key': register.private_key,
            'funds': blockchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Loading the keys failed.'
        }
        return jsonify(response), 500


@app.route('/balance', methods=['GET'])
def get_balance():
    balance = blockchain.get_balance()
    if balance is not None:
        response = {
            'message': 'Fetched balance successfully.',
            'funds': balance
        }
        return jsonify(response), 200
    else:
        response = {
            'messsage': 'Loading balance failed.',
            'wallet_set_up': register.public_key is not None
        }
        return jsonify(response), 500


@app.route('/broadcast-transaction', methods=['POST'])
def broadcast_transaction():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    required = ['sender', 'recipient', 'amount', 'signature']
    if not all(key in values for key in required):
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    success = blockchain.add_transaction(
        values['recipient'],
        values['sender'],
        values['signature'],
        values['amount'],
        is_receiving=True)
    if success:
        response = {
            'message': 'Successfully added transaction.',
            'transaction': {
                'sender': values['sender'],
                'recipient': values['recipient'],
                'amount': values['amount'],
                'signature': values['signature']
            }
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a transaction failed.'
        }
        return jsonify(response), 500


@app.route('/broadcast-block', methods=['POST'])
def broadcast_block():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    if 'block' not in values:
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    block = values['block']
    if block['index'] == blockchain.chain[-1].index + 1:
        if blockchain.add_block(block):
            response = {'message': 'Block added'}
            return jsonify(response), 201
        else:
            response = {'message': 'Block seems invalid.'}
            return jsonify(response), 409
    elif block['index'] > blockchain.chain[-1].index:
        response = {
            'message': 'Blockchain seems to differ from local blockchain.'}
        blockchain.resolve_conflicts = True
        return jsonify(response), 200
    else:
        response = {
            'message': 'Blockchain seems to be shorter, block not added'}
        return jsonify(response), 409


@app.route('/first-transaction', methods=['POST'])
def bootstrap_transaction():
    n = 0
    for node in register.ring:
        if node['address'] != register.address:
            print(node['public_key'])
            trans ={
                'recipient': node['public_key'],
                'amount': 100
            }
            requests.post('http://localhost:5000/transaction', json=trans)
            n +=1
    requests.post('http://localhost:5000/mine')
    response={'message': 'OK'}
    return jsonify(response), 200

    # blockchain.save_data()


@app.route('/transaction', methods=['POST'])
def add_transaction():
    if register.public_key is None:
        response = {
            'message': 'No wallet set up.'
        }
        return jsonify(response), 400
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data found.'
        }
        return jsonify(response), 400
    required_fields = ['recipient', 'amount']
    if not all(field in values for field in required_fields):
        response = {
            'message': 'Required data is missing.'
        }
        return jsonify(response), 400
    recipient = values['recipient']
    amount = values['amount']
    signature = register.wallet.sign_transaction(register.public_key, recipient, amount)
    success = blockchain.add_transaction(
        recipient, register.public_key, signature, amount)
    if success:
        response = {
            'message': 'Successfully added transaction.',
            'transaction': {
                'sender': register.public_key,
                'recipient': recipient,
                'amount': amount,
                'signature': signature
            },
            'funds': blockchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a transaction failed.'
        }
        return jsonify(response), 500


@app.route('/mine', methods=['POST'])
def mine():
    if blockchain.resolve_conflicts:
        response = {'message': 'Resolve conflicts first, block not added!'}
        return jsonify(response), 409
    block = blockchain.mine_block()
    if block is not None:
        dict_block = block.__dict__.copy()
        dict_block['transactions'] = [
            tx.__dict__ for tx in dict_block['transactions']]
        response = {
            'message': 'Block added successfully.',
            'block': dict_block,
            'funds': blockchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Adding a block failed.',
            'wallet_set_up': register.public_key is not None
        }
        return jsonify(response), 500


@app.route('/resolve-conflicts', methods=['POST'])
def resolve_conflicts():
    replaced = blockchain.resolve()
    if replaced:
        response = {'message': 'Chain was replaced!'}
    else:
        response = {'message': 'Local chain kept!'}
    return jsonify(response), 200


@app.route('/transactions', methods=['GET'])
def get_open_transaction():
    transactions = blockchain.get_open_transactions()
    dict_transactions = [tx.__dict__ for tx in transactions]
    return jsonify(dict_transactions), 200


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_snapshot = blockchain.chain
    dict_chain = [block.__dict__.copy() for block in chain_snapshot]
    for dict_block in dict_chain:
        dict_block['transactions'] = [
            tx.__dict__ for tx in dict_block['transactions']]
    return jsonify(dict_chain), 200


@app.route('/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data attached.'
        }
        return jsonify(response), 400
    if 'node' not in values:
        response = {
            'message': 'No node data found.'
        }
        return jsonify(response), 400
    node = values['node']
    blockchain.add_peer_node(node)
    response = {
        'message': 'Node added successfully.',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 201


@app.route('/node/<node_url>', methods=['DELETE'])
def remove_node(node_url):
    if node_url == '' or node_url is None:
        response = {
            'message': 'No node found.'
        }
        return jsonify(response), 400
    blockchain.remove_peer_node(node_url)
    response = {
        'message': 'Node removed',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 200


@app.route('/nodes', methods=['GET'])
def get_nodes():
    nodes = blockchain.get_peer_nodes()
    response = {
        'all_nodes': nodes
    }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    parser.add_argument('-b', '--bootstrap', action='store_true')
    parser.add_argument('-n', '--nodes', type=int, default=2)
    args = parser.parse_args()
    port = args.port
    node_id = port - 5000
    is_bootstrap = args.bootstrap
    nodes_number = args.nodes
    address = 'localhost:' + str(port)
    register = Register(node_id, address)
    #Initializing
    cache.set('counter', 1)
    cache.set('node', register)
    cache.set('nodes_number', nodes_number)
    if not is_bootstrap:
        data = {
            'address': address,
            'public_key': register.public_key,
        }
        resp = requests.post('http://localhost:5000/register', json=data).json()
        print(resp)
        blockchain = Blockchain(register.public_key, register.private_key, node_id, nodes_number)
        app.run(host='0.0.0.0', port=node_id+5000, threaded=True)
    else:
        # The bootstrapper node cant post himself since he hasn't yet started
        register.register_node_to_ring({
            'address': address,
            'public_key': register.public_key,
            'id': 0
        })
        cache.set('node', register)
        blockchain = Blockchain(register.public_key, register.private_key, 0, nodes_number)
        app.run(host='0.0.0.0', port=node_id+5000, threaded=True)
