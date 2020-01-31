# SATORI v1.0b
SATORI is a Self-ATtention based deep learning model to capture Regulatory element Interactions in genomic sequences. It can be used to infer a global landscape of interactions in a given genomic dataset, without a computationally-expensive post-processing step.

## Dependency
SATORI is written in python 3. The following packages are required (the version used is provided):  
PyTorch (version 1.2.0)  
scikit-learn (vresion 0.21.3)  
scipy (version 1.4.1)  
numpy (version 1.17.2)  
pandas (version 0.25.1)  
statsmodels (version 0.9.0)  
matplotlib (vresion 3.1.1)  
fastprogress (version 0.1.21)  
biopython (version 1.75)  
bottleneck (version 1.3.1)

## Usage
```
usage: satori.py [-h] [-v] [-o DIRECTORY] [-m MODE] [--deskload]
                 [-w NUMWORKERS] [--splittype SPLITTYPE]
                 [--splitperc SPLITPERC] [--motifanalysis]
                 [--scorecutoff SCORECUTOFF] [--tomtompath TOMTOMPATH]
                 [--database TFDATABASE] [--annotate ANNOTATETOMTOM] [-a] [-i]
                 [-b INTBACKGROUND] [--attncutoff ATTNCUTOFF]
                 [--intseqlimit INTSEQLIMIT] [-s] [--considertophit]
                 [--numlabels NUMLABELS] [--tomtomdist TOMTOMDIST]
                 [--tomtompval TOMTOMPVAL] [--testall]
                 inputprefix hparamfile

Main deepSAMIREI script.

positional arguments:
  inputprefix           Input file prefix for the data and the corresponding
                        fasta file (sequences). Make sure the sequences are in
                        .fa format whereas the metadata is tab delimited .txt
                        format.
  hparamfile            Name of the hyperparameters file to be used.

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         verbose output [default is quiet running]
  -o DIRECTORY, --outDir DIRECTORY
                        output directory
  -m MODE, --mode MODE  Mode of operation: train or test.
  --deskload            Load dataset from desk. If false, the data is
                        converted into tensors and kept in main memory (not
                        recommended for large datasets).
  -w NUMWORKERS, --numworkers NUMWORKERS
                        Number of workers used in data loader. For loading
                        from the desk, use more than 1 for faster fetching.
                        Also, this also determines number of workers used when
                        inferring interactions.
  --splittype SPLITTYPE
                        Either to use a percantage of data for valid,test or
                        use specific chromosomes. In the later case, provide
                        chrA,chrB for valid,test. Default value is percent and
                        --splitperc value will be used.
  --splitperc SPLITPERC
                        Pecentages of test, and validation data splits, eg. 10
                        for 10 percent data used for testing and validation.
  --motifanalysis       Analyze CNN filters for motifs and search them against
                        known TF database.
  --scorecutoff SCORECUTOFF
                        In case of binary labels, the positive probability
                        cutoff to use.
  --tomtompath TOMTOMPATH
                        Provide path to where TomTom (from MEME suite) is
                        located.
  --database TFDATABASE
                        Provide path to the MEME TF database against which the
                        CNN motifs are searched.
  --annotate ANNOTATETOMTOM
                        Annotate tomtom motifs. The options are: 1. path to
                        annotation file, 2. No (not to annotate the output)
  -a, --attnfigs        Generate Attention (matrix) figures for every test
                        example.
  -i, --interactions    Self attention based feature(TF) interactions
                        analysis.
  -b INTBACKGROUND, --background INTBACKGROUND
                        Background used in interaction analysis: shuffle (for
                        di-nucleotide shuffled sequences with embedded
                        motifs.), negative (for negative test set). Default is
                        not to use background (and significance test).
  --attncutoff ATTNCUTOFF
                        Attention cutoff value to use. A filter-filter
                        interaction profile is discarded if the maximum in
                        that profile is less than this cutoff.
  --intseqlimit INTSEQLIMIT
                        A limit on number of input sequences to test. Default
                        is -1 (use all input sequences that qualify).
  -s, --store           Store per batch attention and CNN outpout matrices. If
                        false, they are kept in the main memory.
  --considertophit      [TO BE ADDED] Consider only the top matching
                        TF/regulatory element for a filter (from TomTom
                        results).
  --numlabels NUMLABELS
                        Number of labels. 2 for binary (default). For multi-
                        class, multi label problem, can be more than 2.
  --tomtomdist TOMTOMDIST
                        TomTom distance parameter (pearson, kullback, ed etc).
                        Default is pearson. See TomTom help from MEME suite.
  --tomtompval TOMTOMPVAL
                        Adjusted p-value cutoff from TomTom. Default is 0.05.
  --testall             Test on the entire dataset, including the training and
                        validation sets (default False). Useful for
                        interaction/motif analysis.
```
