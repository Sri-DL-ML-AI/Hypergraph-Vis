from flask import render_template,request, url_for, jsonify, redirect, Response, send_from_directory
from app import app
from app import APP_STATIC
from app import APP_ROOT
import json
import numpy as np
import pandas as pd
import hypernetx as hnx
import re
import matplotlib.pyplot as plt
import networkx as nx
from tqdm import tqdm
from os import path

def process_graph_edges(edge_str: str):
    """
    Convert a string representation of the hypergraph into a python dictionary

    :param edge_str: string representation of the hypergraph
    :type edge_str: str
    :return: dictionary representing the hypergraph
    :rtype: dict
    """

    edge_str = edge_str.strip().replace('\'', '\"')
    converted_edge_str = edge_str[1:-1].replace('{', '[').replace('}', ']')
    return json.loads('{' + converted_edge_str + '}')

def process_hypergraph(hyper_data: str):

    hgraphs = []

    # Separate the hypergraphs based on this regex:
    # newline followed by one or more whitespace followed by newline
    file_contents = re.split(r'\n\s+\n', hyper_data)

    num_hgraphs = len(file_contents)

    for i in tqdm(range(0, num_hgraphs)):
        # The name and graph are separated by '='
        graph_name, graph_dict = file_contents[i].split('=')
        graph_dict = process_graph_edges(graph_dict)
        # print(graph_name)
        # print(graph_dict)
        # hgraphs.append({'graph_dict':graph_dict, 'graph_name':graph_name})
        hgraphs.append(hnx.Hypergraph(graph_dict, name=graph_name))
    # print(hgraphs)

    return hgraphs

def convert_to_line_graph(hypergraph):
    print(hypergraph)
    # Line-graph is a NetworkX graph
    line_graph = nx.Graph()

    # Nodes of the line-graph are nodes of the dual graph
    # OR equivalently edges of the original hypergraph
    [line_graph.add_node(edge, vertices=list(vertices)) for edge, vertices in hypergraph.incidence_dict.items()]

    node_list = list(hypergraph.edges)

    # For all pairs of edges (e1, e2), add edges such that
    # intersection(e1, e2) is not empty
    for node_idx_1, node1 in enumerate(node_list):
        for node_idx_2, node2 in enumerate(node_list[node_idx_1 + 1:]):
            vertices1 = hypergraph.edges[node1].elements
            vertices2 = hypergraph.edges[node2].elements
            # Compute the intersection size
            intersection_size = len(set(vertices1) & set(vertices2))
            if intersection_size > 0:
                line_graph.add_edge(node1, node2, intersection_size=str(intersection_size))
    line_graph = nx.readwrite.json_graph.node_link_data(line_graph)
    return line_graph

def write_d3_graph(graph, path):
    # Write to d3 like graph format
    node_link_json = nx.readwrite.json_graph.node_link_data(graph)
    # print(node_link_json)
    with open(path, 'w') as f:
        f.write(json.dumps(node_link_json, indent=4))

def find_cc_index(components, vertex_id):
    for i in range(len(components)):
        if vertex_id in components[i]:
            return i

def compute_barcode(graph_data):
    # with open(graph_path) as json_file:
        # data = json.load(json_file)
    nodes = graph_data['nodes']
    links = graph_data['links']
    components = []
    barcode = []
    for node in nodes:
        components.append([node['id']])
    for link in links:
        link['intersection_size'] = int(link['intersection_size'])
    links = sorted(links, key=lambda item: 1 / item['intersection_size'])
    for link in links:
        source_id = link['source']
        target_id = link['target']
        weight = 1 / link['intersection_size']
        source_cc_idx = find_cc_index(components, source_id)
        target_cc_idx = find_cc_index(components, target_id)
        if source_cc_idx != target_cc_idx:
            source_cc = components[source_cc_idx]
            target_cc = components[target_cc_idx]
            components = [components[i] for i in range(len(components)) if i not in [source_cc_idx, target_cc_idx]]
            components.append(source_cc + target_cc)
            barcode.append({'birth': 0, 'death': weight, 'edge': link})
    for cc in components:
        barcode.append({'birth': 0, 'death': -1, 'edge': 'undefined'})
    return barcode


@app.route('/')
@app.route('/Hypergraph-Vis-app')
def index():
    return render_template('HyperVis.html')

@app.route('/import', methods=['POST','GET'])
def import_file():
    jsdata = request.get_data().decode('utf-8')
    hgraphs = process_hypergraph(jsdata)
    hgraph = hgraphs[0]
    # lgraph = convert_to_line_graph(hnx.Hypergraph(hgraph['graph_dict'], name=hgraph['graph_name']))
    lgraph = convert_to_line_graph(hgraph)
    hgraph = nx.readwrite.json_graph.node_link_data(hgraph.bipartite())
    # write_d3_graph(hgraph.bipartite(), path.join(APP_STATIC,"uploads/hypergraph.json"))
    # write_d3_graph(lgraph, path.join(APP_STATIC,"uploads/linegraph.json"))
    barcode = compute_barcode(lgraph)
    # with open(path.join(APP_STATIC,"uploads/barcode.json"), 'w') as f:
        # f.write(json.dumps({'barcode': barcode}, indent=4))
    # filename = path.join(APP_STATIC,"assets/",jsdata.filename)
    # with open(filename) as f:
    #     data = json.load(f)
    # f.close()
    print(barcode)
    return jsonify(hyper_data=hgraph, line_data=lgraph, barcode_data=barcode)

