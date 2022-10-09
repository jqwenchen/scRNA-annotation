import gc

import numpy as np
import itertools
import argparse
import os
import scanpy as sc
import numpy as np
import torch


def str2bool(v):
    """
    Helper to pass boolean arguements.
    Extracted from: https://stackoverflow.com/questions/15008758/parsing-boolean-values-with-argparse
    Author: @Maxim
    """

    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def parse_args():
    parser=argparse.ArgumentParser()
    parser.add_argument('-c', '--cuda', required=False, type=str2bool,
                        default=False, help="boolean, optional, if use GPU for neural network training, default False")

def main(args):
    args = parse_args()
    use_cuda = args.cuda
    device = torch.device("cuda" if use_cuda else "cpu")
    if use_cuda:
        pin_memory = True
        non_blocking = True
    else:
        pin_memory = False
        non_blocking = False




def gen_tf_gene_table(genes, tf_list, dTD):
    """
#genes_upper, pathway_list, pathway2gene)
    Adapted from:
    Author: Jun Ding
    Project: SCDIFF2
    Ref: Ding, J., Aronow, B. J., Kaminski, N., Kitzmiller, J., Whitsett, J. A., & Bar-Joseph, Z.
    (2018). Reconstructing differentiation networks and their regulation from time series
    single-cell expression data. Genome research, 28(3), 383-395.

    """
    gene_names = [g.upper() for g in genes]
    TF_names = [g.upper() for g in tf_list]
    tf_gene_table = dict.fromkeys(tf_list)

    for i, tf in enumerate(tf_list):
        tf_gene_table[tf] = np.zeros(len(gene_names))
        _genes = dTD[tf]

        _existed_targets = list(set(_genes).intersection(gene_names))
        _idx_targets = map(lambda x: gene_names.index(x), _existed_targets)

        for _g in _idx_targets:
            tf_gene_table[tf][_g] = 1

    del gene_names
    del TF_names
    del _genes
    del _existed_targets
    del _idx_targets

    gc.collect()

    return tf_gene_table


def getGeneSetMatrix(_name, genes_upper, gene_sets_path):
    """

    Adapted from:
    Author: Jun Ding
    Project: SCDIFF2
    Ref: Ding, J., Aronow, B. J., Kaminski, N., Kitzmiller, J., Whitsett, J. A., & Bar-Joseph, Z.
    (2018). Reconstructing differentiation networks and their regulation from time series
    single-cell expression data. Genome research, 28(3), 383-395.

    """
    if _name[-3:] == 'gmt': # c5.go.bp.v7.4.symbols.gmt
        print(f"GMT file {_name} loading ... ")
        filename = _name
        filepath = os.path.join(gene_sets_path, f"{filename}")

        with open(filepath) as genesets:
            pathway2gene = {line.strip().split("\t")[0]: line.strip().split("\t")[2:]
                            for line in genesets.readlines()}

        print(len(pathway2gene))
        # for i, (k,v) in enumerate(pathway2gene.items()):
        #     print({k:v}, end="")
        #     if i == 4:
        #         print()
        #         break
        gs = []
        for k, v in pathway2gene.items():
            gs += v

        print(f"Number of genes in {_name} {len(set(gs).intersection(genes_upper))}")

        pathway_list = pathway2gene.keys()
        # print(pathway_list)
        pathway_gene_table = gen_tf_gene_table(genes_upper, pathway_list, pathway2gene)
        # print(pathway_gene_table)
        gene_set_matrix = np.array(list(pathway_gene_table.values()))
        keys = pathway_gene_table.keys()

        del pathway2gene
        del gs
        del pathway_list
        del pathway_gene_table

        gc.collect()


    elif _name == 'TF-DNA':

        # get TF-DNA dictionary
        # TF->DNA
        def getdTD(tfDNA):
            dTD = {}
            with open(tfDNA, 'r') as f:
                tfRows = f.readlines()
                tfRows = [item.strip().split() for item in tfRows]
                for row in tfRows:
                    itf = row[0].upper()
                    itarget = row[1].upper()
                    if itf not in dTD:
                        dTD[itf] = [itarget]
                    else:
                        dTD[itf].append(itarget)

            del tfRows
            del itf
            del itarget
            gc.collect()

            return dTD

        from collections import defaultdict

        def getdDT(dTD):
            gene_tf_dict = defaultdict(lambda: [])
            for key, val in dTD.items():
                for v in val:
                    gene_tf_dict[v.upper()] += [key.upper()]

            return gene_tf_dict

        tfDNA_file = os.path.join(gene_sets_path, f"Mouse_TF_targets.txt")
        dTD = getdTD(tfDNA_file)
        dDT = getdDT(dTD)

        tf_list = list(sorted(dTD.keys()))
        tf_list.remove('TF')

        tf_gene_table = gen_tf_gene_table(genes_upper, tf_list, dTD)
        gene_set_matrix = np.array(list(tf_gene_table.values()))
        keys = tf_gene_table.keys()

        del dTD
        del dDT
        del tf_list
        del tf_gene_table

        gc.collect()

    else:
        gene_set_matrix = None

    return gene_set_matrix, keys



if __name__ == '__main__':
    geneSetsPath = "/home/jackie/PycharmProjects/UNIFAN/tutorails/gene_sets"
    prior_name = 'c5.go.bp.v7.4.symbols.gmt+c2.cp.v7.4.symbols.gmt+TF-DNA'
    mouse = sc.read('../mouse/input/Limb_Muscle_facts_processed_3m.h5ad', dtype='float64', backed="r")
    genes = mouse.var.index.values
    genes_upper = [g.upper() for g in genes]

    if '+' in prior_name:
        prior_names_list = prior_name.split('+')

    if '+' in prior_name:
        _matrix_list = []
        _keys_list = []
        for _name in prior_names_list:
            _matrix, _keys = getGeneSetMatrix(_name, genes_upper, geneSetsPath)
            # print("matrix", _matrix)
            # print("keys", _keys)
            _matrix_list.append(_matrix)
            _keys_list.append(_keys)

        gene_set_matrix = np.concatenate(_matrix_list, axis=0)
        print("original", gene_set_matrix)
        genes_covered = np.sum(gene_set_matrix, axis=0)
        print(genes_covered)  #[  0.  46.  38. ... 169.  19.  59.]
        gene_covered_matrix = gene_set_matrix[:, genes_covered != 0]
        print("shape of gene covered matrix", gene_covered_matrix.shape)
        print("processed", gene_covered_matrix)

        keys_all = list(itertools.chain(*_keys_list))
        #print(keys_all)