## SecuML
## Copyright (C) 2016-2017  ANSSI
##
## SecuML is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## SecuML is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with SecuML. If not, see <http://www.gnu.org/licenses/>.

import datetime
from flask import render_template, jsonify
import json
import pandas as pd

from SecuML_web.base import app, db, cursor, user_exp

from SecuML.ActiveLearning.Iteration import Iteration
from SecuML.Data import labels_tools
from SecuML.Experiment.ActiveLearningExperiment import ActiveLearningExperiment
from SecuML.Experiment import ExperimentFactory
from SecuML.Plots.BarPlot import BarPlot
from SecuML.Plots.PlotDataset import PlotDataset
from SecuML.Tools import colors_tools
from SecuML.Tools import dir_tools
from SecuML.Tools import matrix_tools

from CeleryApp.activeLearningTasks import runNextIteration as celeryRunNextIteration
from CeleryApp.activeLearningTasks import checkAnnotationQueriesAnswered as celeryCheckAnnotationQueriesAnswered

@app.route('/currentAnnotations/<project>/<dataset>/<experiment_id>/<iteration>/')
def currentAnnotations(project, dataset, experiment_id, iteration):
    page = render_template('ActiveLearning/current_annotations.html', project = project)
    if user_exp:
        experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id,
                                                             db, cursor)
        filename  = dir_tools.getExperimentOutputDirectory(experiment)
        filename += 'user_actions.log'
        file_exists = dir_tools.checkFileExists(filename)
        mode = 'a' if file_exists else 'w'
        to_print = [datetime.datetime.now(), 'displayAnnotatedInstances']
        to_print = map(str, to_print)
        to_print = ','.join(to_print)
        with open(filename, mode) as f:
            print >>f, to_print
    return page

@app.route('/editFamilies/<project>/<dataset>/<experiment_id>/')
def editFamilies(project, dataset, experiment_id):
    return render_template('ActiveLearning/edit_families.html')

@app.route('/getFamiliesBarplot/<project>/<dataset>/<experiment_id>/<iteration>/<label>/')
def getFamiliesBarplot(project, dataset, experiment_id, iteration, label):
    experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id,
                                                         db, cursor)
    experiment_label_id = experiment.experiment_label_id
    if iteration == 'None':
        iteration = None
    family_counts = labels_tools.getFamiliesCounts(cursor, experiment_label_id,
                                                   iteration_max = iteration,
                                                   label = label)
    df = pd.DataFrame({'families': family_counts.keys(),
                       'counts': [family_counts[k] for k in family_counts.keys()]})
    matrix_tools.sortDataFrame(df, 'families', ascending = True, inplace = True)
    barplot = BarPlot(list(df['families']))
    dataset = PlotDataset(list(df['counts']), 'Num. Instances')
    dataset.setColor(colors_tools.getLabelColor(label))
    barplot.addDataset(dataset)
    return jsonify(barplot.toJson())

@app.route('/currentAnnotationIteration/<project>/<dataset>/<experiment_id>/')
def currentAnnotationIteration(project, dataset, experiment_id):
    db.commit()
    experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id,
            db, cursor)
    return str(experiment.getCurrentIteration())

@app.route('/getActiveLearningValidationConf/<project>/<dataset>/<experiment_id>/')
def getActiveLearningValidationConf(project, dataset, experiment_id):
    experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id,
            db, cursor)
    return jsonify(experiment.validation_conf.toJson())

@app.route('/getIterationSupervisedExperiment/<project>/<dataset>/<experiment_id>/<iteration>/')
def getIterationSupervisedExperiment(project, dataset, experiment_id, iteration):
    experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id, db, cursor)
    active_learning = Iteration(experiment, int(iteration))
    binary_multiclass = 'multiclass'
    if 'binary' in experiment.conf.models_conf.keys():
        binary_multiclass = 'binary'
    models_exp_file = active_learning.output_directory + 'models_experiments.json'
    with open(models_exp_file, 'r') as f:
        models_exp = json.load(f)
    return str(models_exp[binary_multiclass])

@app.route('/runNextIteration/<project>/<dataset>/<experiment_id>/<iteration_number>/')
def runNextIteration(project, dataset, experiment_id, iteration_number):
    res = str(celeryRunNextIteration.s().apply_async())
    if user_exp:
        experiment = ExperimentFactory.getFactory().fromJson(project, dataset, experiment_id,
                                                             db, cursor)
        filename  = dir_tools.getExperimentOutputDirectory(experiment)
        filename += 'user_actions.log'
        file_exists = dir_tools.checkFileExists(filename)
        mode = 'a' if file_exists else 'w'
        to_print = [datetime.datetime.now(), 'nextIteration', iteration_number]
        to_print = map(str, to_print)
        to_print = ','.join(to_print)
        with open(filename, mode) as f:
            print >>f, to_print
    return res

@app.route('/checkAnnotationQueriesAnswered/<project>/<dataset>/<experiment_id>/<iteration_number>/')
def checkAnnotationQueriesAnswered(project, dataset, experiment_id, iteration_number):
    res = celeryCheckAnnotationQueriesAnswered.s().apply_async().get()
    return str(res)