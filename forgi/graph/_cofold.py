"""
Take a BulgeGraph and return a copy of it with cofold splitpoints inserted.
"""
import logging
from ._graph_construction import remove_vertex

log = logging.getLogger(__name__)

def split_at_cofold_cutpoints(bg, cutpoints):
    """
    Multiple sequences should not be connected along the backbone.

    We have constructed the bulge graph, as if they were connected along the backbone, so
    now we have to split it.
    """

    for splitpoint in cutpoints:
        element_left = bg.get_node_from_residue_num(splitpoint)
        element_right = bg.get_node_from_residue_num(splitpoint+1)
        if element_left[0] in "ft" or element_right[0] in "ft":
            if element_left[0]=="t" and element_left[0]!="t":
                continue # Splitpoint already implemented
            elif element_right[0]=="f" and element_left[0]!="f":
                continue # Splitpoint already implemented
            else:
                #No cofold structure. First sequence is disconnected from rest
                e = GraphConstructionError("Cannot create BulgeGraph. Found two sequences not "
                        "connected by any base-pair.")
                with log_to_exception(log, e):
                    log.error("Trying to split between %s and %s", element_left, element_right)
                raise e
            return
        elif element_left[0]=="i" or element_right[0]=="i":
            bg._split_interior_loop(splitpoint, element_left, element_right)
        elif element_left != element_right:
            bg._split_between_elements(splitpoint, element_left, element_right)
        elif element_left[0]=="s":
            bg._split_inside_stem(splitpoint, element_left)
        else:
            bg._split_inside_loop(splitpoint, element_left)

    if not _is_connected(bg):
        raise GraphConstructionError("Cannot create BulgeGraph. Found two sequences not connected by any "
                         " base-pair.")

def _is_connected(bg):
    start_node = list(bg.defines.keys())[0]
    known_nodes = set([start_node])
    pending = list(bg.edges[start_node])
    while pending:
        next_node = pending.pop()
        if next_node in known_nodes:
            continue
        pending.extend(bg.edges[next_node])
        known_nodes.add(next_node)
    log.info("Testing connectivity: connected component =?= all nodes:\n{} =?= {}".format(list(sorted(known_nodes)), list(sorted(set(bg.defines.keys())))))
    return known_nodes == set(bg.defines.keys())


def stem_length(bg, key):
    d = bg.defines[key]
    assert key[0] == 's'
    return (d[1] - d[0]) + 1

def _split_between_elements(bg, splitpoint, element_left, element_right):
    if element_left[0] in "mh":
        next3 = _next_available_element_name(bg, "t")
        bg.relabel_node(element_left, next3)
        if element_left[0]!="h":
            bg._remove_edge(next3, element_right)
    elif element_right[0] in "mh":
        next5 = _next_available_element_name(bg, "f")
        bg.relabel_node(element_right, next5)
        if element_right[0]!="h":
            bg._remove_edge(next5, element_left)
    else:
        assert element_left[0]=="s" and element_right[0]=="s"
        #Zero-length i or m element!
        connections = bg.edges[element_left] & bg.edges[element_right]
        if len(connections)==0:
            raise GraphConstructionError("Cannot split at cofold cutpoint. Missing connection between {} and {}.".format(element_left, element_right))
        else:
            for connection in connections:
                if connection[0]=="i":
                    break
                if not bg.defines[connection]:
                    ad_define = bg.define_a(connection)
                    if ad_define[0]==splitpoint:
                        break
            else:
                raise GraphConstructionError("Cannot split at cofold cutpoint. No suitable connection between {} and {}.".format(element_left, element_right))
        if connection[0] == "m":
            #Just remove it without replacement
            remove_vertex(bg, connection)
        else:
            assert connection[0]=="i"
            #Replace i by ml (this is then located on the other strand than the splitpoint)
            nextML = _next_available_element_name(bg, "m")
            assert nextML not in bg.defines
            bg.relabel_node(connection, nextML)

def _split_inside_loop(bg, splitpoint, element):
    if element[0] in "hm":
        from_, to_ = bg.defines[element]
        stem_left = bg.get_node_from_residue_num(from_-1)
        stem_right = bg.get_node_from_residue_num(to_+1)

        next3 = _next_available_element_name(bg, "t")
        next5 = _next_available_element_name(bg, "f")
        bg.defines[next3]=[from_, splitpoint]
        bg.defines[next5]=[splitpoint+1, to_]
        _add_edge(bg, stem_left, next3)
        _add_edge(bg, next5, stem_right)
        remove_vertex(bg, element)
    else:
        assert False

def _split_inside_stem(bg, splitpoint, element):
    assert element[0]=="s"
    log.debug("Split inside stem %s at %s", element, splitpoint)
    if splitpoint == bg.defines[element][1]:
        #Nothing needs to be done. 2 strands split at end
        log.debug("Nothing to do")
        return
    elif splitpoint<bg.defines[element][1]:
        # Splitpoint in forward strand:
        define1 = [bg.defines[element][0], splitpoint, bg.pairing_partner(splitpoint), bg.defines[element][3]]
        define2 = [ splitpoint+1, bg.defines[element][1], bg.defines[element][2], bg.pairing_partner(splitpoint+1)]
        log.debug("Split in forward strand")
    else:
        # Splitpoint in backwards strand:
        define1 = [bg.defines[element][0], bg.pairing_partner(splitpoint+1), splitpoint+1, bg.defines[element][3]]
        define2 = [ bg.pairing_partner(splitpoint), bg.defines[element][1], bg.defines[element][2], splitpoint]
        log.debug("Split in backwards strand")
    edges1=[]
    edges2=[]

    for edge in bg.edges[element]:
        log.debug("Checking edge %s with define %s connected to %s", edge, bg.defines[edge], bg.edges[edge])
        if max(bg.flanking_nucleotides(edge))==define1[0] or min(bg.flanking_nucleotides(edge))==define1[3]:
            edges1.append(edge)
        elif max(bg.flanking_nucleotides(edge))==define2[2] or min(bg.flanking_nucleotides(edge))==define2[1]:
            edges2.append(edge)
        else:
            log.error("For stem %s with define %s and cutpoint %s:", element, bg.defines[element], splitpoint)
            log.error("Edge {}, with flanking nts {}, define1 {}, define2 {}".format(edge, bg.flanking_nucleotides(edge), define1, define2))
            assert False
    remove_vertex(bg, element)
    nextS1 = _next_available_element_name(bg, "s")
    bg.defines[nextS1]=define1
    nextM = _next_available_element_name(bg, "m")
    bg.defines[nextM]=[]
    nextS2 = _next_available_element_name(bg, "s")
    bg.defines[nextS2]=define2

    for e1 in edges1:
        bg.edges[e1].add(nextS1)
    for e2 in edges2:
        bg.edges[e2].add(nextS2)
    edges1.append(nextM)
    edges2.append(nextM)
    bg.edges[nextS1]=set(edges1)
    bg.edges[nextS2]=set(edges2)
    bg.edges[nextM]=set([nextS1, nextS2])

def _next_available_element_name(bg, element_type):
    """
    :param element_type: A single letter ("t", "f", "s"...)
    """
    i=0
    while True:
        name="{}{}".format(element_type, i)
        if name not in bg.defines:
            return name
        i+=1

def _remove_edge(bg, from_element, to_element):
    bg.edges[from_element].remove(to_element)
    bg.edges[to_element].remove(from_element)

def _add_edge(bg, from_element, to_element):
    bg.edges[from_element].add(to_element)
    bg.edges[to_element].add(from_element)

def _split_interior_loop_at_side(bg, splitpoint, strand, other_strand, stems):
    """
    Called by bg._split_at_cofold_cutpoints
    """
    nextML = _next_available_element_name(bg, "m")
    nextA = _next_available_element_name(bg, "t")
    nextB = _next_available_element_name(bg, "f")

    if other_strand[0]>other_strand[1]:
        bg.defines[nextML] = []
    else:
        bg.defines[nextML] = other_strand
    _add_edge(bg, nextML, stems[0])
    _add_edge(bg, nextML, stems[1])

    if splitpoint >= strand[0]:
        bg.defines[nextA]=[strand[0], splitpoint]
        _add_edge(bg, nextA,stems[0])
    if splitpoint < strand[1]:
        bg.defines[nextB]=[splitpoint+1, strand[1]]
        _add_edge(bg, nextB, stems[1])

def _split_interior_loop(bg, splitpoint, element_left, element_right):
    if element_left[0]=="i":
        iloop = element_left
    elif element_right[0]=="i":
        iloop=element_right
    else:
        assert False
    c = bg.connections(iloop)
    s1 = bg.defines[c[0]]
    s2 = bg.defines[c[1]]
    forward_strand = [ s1[1]+1, s2[0]-1 ]
    back_strand = [ s2[3]+1, s1[2]-1 ]
    if forward_strand[0]-1 <= splitpoint <= forward_strand[1]:
        #Split forward strand, relabel backwards strand to multiloop.
        bg._split_interior_loop_at_side(splitpoint, forward_strand, back_strand, c)
    elif back_strand[0] -1 <= splitpoint <= back_strand[1]:
        bg._split_interior_loop_at_side(splitpoint, back_strand, forward_strand, [c[1], c[0]])
    else:
        assert False
    remove_vertex(bg, iloop)
