# -*- coding: utf-8 -*-

"""
    CRF with different types of nodes
    
    NOTE: this is an abstract class. Do not use directly.

    Copyright Xerox(C) 2017 JL. Meunier

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
    
    Developed  for the EU project READ. The READ project has received funding 
    from the European Union�s Horizon 2020 research and innovation programme 
    under grant agreement No 674943.
    
"""
import numpy as np

from .base import StructuredModel
from ..inference import get_installed


class InconsistentLabel(Exception):
    pass

class TypedCRF(StructuredModel):
    """Abstract base class"""
    def __init__(self
                 , n_types                  #how many node type?
                 , l_n_states               #how many labels   per node type?
                 , l_n_features             #how many features per node type?
                 , inference_method="ad3+" 
                 , l_class_weight=None):    #class_weight      per node type or None           <list of array-like> or None
        
        StructuredModel.__init__(self)
        
        if inference_method is None:
            # get first in list that is installed
            inference_method = get_installed(['ad3+', 'ad3', 'max-product', 'lp'])[0]
        self.inference_method = inference_method
        self.inference_calls = 0
        self.inference_exception = False    #if inference cannot be done, raises an exception
        
        if len(l_n_states)   != n_types:
            raise ValueError("Expected 1 number of states per node type.")
        if l_n_features != None and len(l_n_features) != n_types:
            raise ValueError("Expected 1 number pf features per node type.")
        self.n_types      = n_types
        self.l_n_states   = l_n_states
        self._n_states    = sum(l_n_states)     #total number of states
        self.l_n_features = l_n_features
        self._n_features  = sum(self.l_n_features)   #total number of (node) features
        
        #number of typextype states, or number of states per type of edge
        self.l_n_edge_states = [ n1 * n2 for n1 in self.l_n_states for n2 in self.l_n_states ]

#         #Caching some heavily used values
#         self._get_unary_potentials_initialize()
        
        #class weights:
        # either we get class weights for all types of nodes, or for none of them!
        if l_class_weight:
            if len(l_class_weight) != self.n_types:
                raise ValueError("Expected 1 class weight list per node type.")
            for i, n_states in enumerate(self.l_n_states):
                if len(l_class_weight[i]) != n_states:
                    raise ValueError("Expected 1 class weight per state per node type. Wrong for type %d"%i)
                    
            #class weights are computed by type and simply concatenated
            self.l_class_weight = [np.asarray(class_weight) for class_weight in l_class_weight]
        else:
            self.l_class_weight = [np.ones(n) for n in self.l_n_states]
        self.class_weight = np.hstack(self.l_class_weight)

        self._set_size_joint_feature()

        #internal stuff
        #when putting features in a single sequence, index of 1st state for type i
        self._l_type_startindex = [ sum(self.l_n_states[:i]) for i in range(self.n_types+1)]
        
        #when putting states in a single sequence, index of 1st feature for type i (is at Ith position)
        #we store the slice objects
        self._a_feature_slice_by_typ = np.array([ slice(sum(self.l_n_features[:i]), sum(self.l_n_features[:i+1])) for i in range(self.n_types)])






        
        
        
        #when putting edge states in a single sequence, index of 1st state of an edge of type (typ1, typ2)
        self.a_startindex_by_typ_typ = np.zeros((self.n_types, self.n_types), dtype=np.uint32)
        i_state_start = 0
        for typ1, typ1_n_states in enumerate(self.l_n_states):
            for typ2, typ2_n_states in enumerate(self.l_n_states):
                self.a_startindex_by_typ_typ[typ1,typ2] = i_state_start
                i_state_start += typ1_n_states*typ2_n_states 


    def flatY(self, lX, lY_by_typ):
        """
        It is more convenient to have the Ys grouped by type, as the Xs are.
        Also, having a label starting at 0 for each type.
        
        This method does the job.
        
        lX is a list of X strutured as explained 
        """
        pass
    
    def initialize(self, X, Y=None):
        if isinstance(X, list):
            map(self._check_size_x, X)
            if not (Y is None): map(self._check_size_xy, X, Y)
        else:
            self._check_size_x(X)
            self._check_size_xy(X, Y)
    
    def setInferenceException(self, bRaiseExceptionWhenInferenceNotSuccessful):
        """
        set exception on or off when inference canoot be done.
        """
        self.inference_exception = bRaiseExceptionWhenInferenceNotSuccessful
        return self.inference_exception
    
    def _set_size_joint_feature(self):
        """
        We have:
        - 1 weight per node feature per label per node type
        """
        self.size_unaries = sum(  n_states * n_features for n_states, n_features in zip(self.l_n_states, self.l_n_features) )
        self.size_joint_feature = self.size_unaries

    def __repr__(self):
        return ("%s(n_states: %s, inference_method: %s)"
                % (type(self).__name__, self.l_n_states,
                   self.inference_method))

    def _check_size_x(self, x):
        #node_features are [  i_in_typ -> features ]
        l_node_features = self._get_node_features(x)
        if len(l_node_features) != self.n_types:
            raise ValueError("Expected one node feature array per node type.")
        
        for typ, typ_features in enumerate(l_node_features):
            if typ_features.shape[1] != self.l_n_features[typ]:
                raise ValueError("Expected %d features for type %d"%(self.l_n_features[typ], typ))

        #edges
        l_edges = self._get_edges(x)
        for edges in l_edges:
            if edges is None: continue
            if edges.ndim != 2:
                raise ValueError("Expected a 2 dimensions edge arrays")
            if edges.shape[1] != 2:
                raise ValueError("Expected 2 columns in edge arrays")

        for typ1,typ2 in self._iter_type_pairs():
            edges = self._get_edges_by_type(x, typ1, typ2) 
        
            if edges is None or len(edges) == 0: continue
            #edges should point to valid node indices
            nodes1, nodes2 = edges[:,0], edges[:,1]
            if min(nodes1) < 0 or min(nodes2) < 0:
                raise ValueError("At least one edge points to negative and therefore invalid node index: type %d to type %d"%(typ1,typ2))
            if max(nodes1) >= l_node_features[typ1].shape[0]:
                raise ValueError("At least one edge starts from a non-existing node index: type %d to type %d"%(typ1,typ2))
            if max(nodes2) >= l_node_features[typ2].shape[0]:
                raise ValueError("At least one edge points to a non-existing node index: type %d to type %d"%(typ1,typ2))    
        return True
    
    def _check_size_xy(self, X, Y):
        if Y is None: return
        
        #make sure Y has the proper length and acceptable labels
        l_node_features = self._get_node_features(X, True)
        
        nb_nodes = sum(nf.shape[0] for nf in l_node_features)
        if Y.shape[0] != nb_nodes:
            raise ValueError("Expected 1 label for each of the %d nodes. Gopt %d labels."%(nb_nodes, Y.shape[0]))
        
        i_start = 0    
        for typ, nf, n_states in zip(range(self.n_types), l_node_features, self.l_n_states):
            nb_nodes = nf.shape[0]
            Y_typ = Y[i_start:i_start+nb_nodes]
            if  np.min(Y_typ) < 0:
                raise ValueError("Got a negative label for type %d"%typ)
#             if np.max(Y_typ) >= n_states:
#                 raise ValueError("Got a label outside of [0, %d] for type %d: %s"%(n_states-1, typ, Y_typ))
            if np.min(Y_typ) < self._l_type_startindex[typ] : raise InconsistentLabel("labels of type %d start at %d"%(typ, self._l_type_startindex[typ]))
            if np.max(Y_typ) >= self._l_type_startindex[typ+1]: raise InconsistentLabel("labels of type %d end at %d"%(typ, self._l_type_startindex[typ+1]-1))
            i_start = i_start + nb_nodes
        return True
        
                    
    def _get_node_features(self, x, bClean=False):
        if bClean:
            #we replace None by empty array with proper shape
            return [ np.empty((0,_n_feat)) if node_features is None else node_features 
                    for (node_features, _n_feat) in zip(x[0], self.l_n_features)]
        else:
            return x[0]
    
    def _get_edges(self, x, bClean=False):
        if bClean:
            return [ np.empty((0,0)) if edges is None or len(edges)==0 else edges for edges in x[1]]
        else:
            return x[1]
    
    def _get_edges_by_type(self, x, typ1, typ2):
        return x[1][typ1*self.n_types+typ2] 

    def _iter_type_pairs(self):
        for typ1 in range(self.n_types):
            for typ2 in range(self.n_types):
                yield (typ1, typ2)
        raise StopIteration


#     def _get_unary_potentials_initialize(self):
#         """
#         pre-compute iteration params
#         """
#     
#         self._cache_unary_potentials = list()
#           
#         i_w, i_states = 0, 0
#         for n_states, n_features in zip(self.l_n_states, self.l_n_features):  
#             i_w2 = i_w + n_states*n_features        #number of weights for the type
#             i_states2 = i_states + n_states         #number of state of that type
#             self._cache_unary_potentials.append( ((i_w,i_w2), (i_states, i_states2), (n_states, n_features)) )
#             i_w, i_states = i_w2, i_states2 
 
    def _get_unary_potentials(self, x, w):
        """Computes unary potentials for x and w.
 
        Parameters
        ----------
        x : tuple
            Instance Representation.
 
        w : ndarray, shape=(size_joint_feature,)
            Weight vector for CRF instance.
 
        Returns
        -------
        unaries : list of ndarray, shape=( n_nodes_typ, n_states_typ )
            Unary weights.
        """
        self._check_size_w(w)
        l_node_features = self._get_node_features(x, True)
 
        l_unary_potentials = []
            
        i_w = 0
        for (features, n_states, n_features) in zip(l_node_features, self.l_n_states, self.l_n_features):  
            n_w = n_states*n_features
            l_unary_potentials.append( np.dot(features, w[i_w:i_w+n_w].reshape(n_states, n_features).T) )
            i_w += n_w
        assert i_w == self.size_unaries
            
        # nodes x features  .  features x states  -->  nodes x states
        return l_unary_potentials
    
#         self._check_size_w(w)
#         l_node_features = self._get_node_features(x)
#  
#         w_unaries = w[:self.size_unaries]
#         a_nodes_states = np.zeros((sum(nf.shape[0] for nf in l_node_features)
#                                    , self._n_states), dtype=w.dtype)
#         i_nodes = 0
#         for features, ((i_w,i_w2), (i_states, i_states2), (n_states, n_features)) in zip(l_node_features, self._cache_unary_potentials):  
#             i_nodes2 = i_nodes + features.shape[0]  #number of nodes of that type
#             a_nodes_states[i_nodes:i_nodes2, i_states:i_states2] = np.dot(features, w_unaries[i_w:i_w2].reshape(n_states, n_features).T)
#             i_nodes = i_nodes2
#         # nodes x features  .  features x states  -->  nodes x states
#         return a_nodes_states
            
