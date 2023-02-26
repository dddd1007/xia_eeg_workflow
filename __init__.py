# Parameters example
# raw_data_path = "/Users/dddd1007/research/Project4_EEG_Volatility_to_Control/data/input/eeg/sub1.cdt"
# savefile_path = "/Users/dddd1007/research/Project4_EEG_Volatility_to_Control/data/output"
# montage_file_path ="/Users/dddd1007/research/Project4_EEG_Volatility_to_Control/data/resource/ch_loc_export_from_eeglab.loc"
# event_file_path = "/Users/dddd1007/research/Project4_EEG_Volatility_to_Control/data/output/exp_event_file/sub1_new_event_file_mne_eve.txt"
# rm_chans_list = ['F1', 'F5', 'CP3']
# input_event_dict = {31: 'con/MC/s', 32: 'inc/MC/s', 33: 'con/MI/s', 34: 'inc/MI/s',
#                     41: 'con/MC/v', 42: 'inc/MC/v', 43: 'con/MI/v', 44: 'inc/MI/v',
#                     98: 'corr_resp', 99: 'wrong_resp'}
# eog_chans = ['HEO', 'VEO']
# sub_num = 1
# tmin = -0.3
# tmax=1.2
# l_freq=1
# h_freq=30
# ica_z_thresh = 1.96

#
# Preprocess EEG data
#


def preprocess_epoch_data(raw_data_path, montage_file_path, event_file_path, savefile_path,
                          input_event_dict: dict, rm_chans_list: list, eog_chans: list, sub_num: int,
                          tmin=-0.3, tmax=1.2, l_freq=1, h_freq=30, ica_z_thresh=1.96,
                          export_to_mne=True):
    import os
    from autoreject import (get_rejection_threshold, AutoReject)
    import mne
    import numpy as np
    os.environ['OPENBLAS_NUM_THREADS'] = '6'

    # Import data
    raw = mne.io.read_raw_curry(raw_data_path, preload=True)

    # Set the channel type
    raw.info['bads'].extend(rm_chans_list)
    raw.set_channel_types(dict(zip(eog_chans, ['eog']*len(eog_chans))))

    # Set the montage
    montage_file = mne.channels.read_custom_montage(montage_file_path)
    raw.set_montage(montage_file)

    # Set the preprocessing setting
    filter_data = raw.copy()

    # Remove channels which are not needed
    # filter_data.drop_channels(rm_chans_list)

    # Filter the data
    filter_data.filter(l_freq, h_freq, n_jobs=6)

    # prepare for ICA
    # reject_para = get_rejection_threshold(epochs_forica)

    # compute ICA
    ica = mne.preprocessing.ICA(n_components=.999, method='picard')
    ica.fit(filter_data)

    # Exclude blink artifact components
    eog_indices, eog_scores = ica.find_bads_eog(
        raw, ch_name=['FP1', 'FP2', 'F8'], threshold=ica_z_thresh)
    muscle_indices, muscle_scores = ica.find_bads_muscle(
        raw, threshold=ica_z_thresh)
    ica.exclude = muscle_indices + eog_indices
    ica.save(os.path.join(savefile_path, 'mne_fif', 'ICA',
             'sub'+str(sub_num) + '-ica.fif'), overwrite=True)
    ica_data = ica.apply(filter_data.copy())

    # Rereference
    ica_data.set_eeg_reference(ref_channels='average')

    # Import Event
    new_event = mne.read_events(event_file_path)
    annot_from_events = mne.annotations_from_events(events=new_event,
                                                    event_desc=input_event_dict,
                                                    sfreq=raw.info['sfreq'],
                                                    orig_time=raw.info['meas_date'])
    ica_data.set_annotations(annot_from_events)

    # Check the event in data
    events, event_dict = mne.events_from_annotations(ica_data)
    ica_data.del_proj()
    epochs = mne.Epochs(ica_data, events, event_dict, tmin, tmax,
                        baseline=(None, 0),  # reject=reject_para,
                        verbose=False, detrend=0, preload=True)

    # Autoreject
    ar = AutoReject(n_jobs=6)
    ar.fit(epochs)  # fit on a few epochs to save time
    epochs_ar, reject_log = ar.transform(epochs, return_log=True)

    # Create evoked data
    conditions = [i for i in input_event_dict.values()]
    if export_to_mne:
        epochs_filename = os.path.join(
            savefile_path, "mne_fif", "sub" + str(sub_num).zfill(2) + '-epo.fif')
        epochs_ar.save(epochs_filename, overwrite=True)

#
# Show the result
#

def generate_evokes(processed_data_list: list, cond1, cond2):
    import mne
    conditions = [cond1, cond2]
    evokes = {}
    for c in conditions:
        evokes[c] = [mne.read_epochs(d)[c].average()
                      for d in processed_data_list]
    return evokes

def generate_diff_evokes(evokes):
    import mne
    diff_evokes = []
    for i in range(len(evokes[list(evokes.keys())[0]])):
        diff_evokes.append(mne.combine_evoked(
            [evokes[list(evokes.keys())[0]][i], evokes[list(evokes.keys())[1]][i]], weights=[1, -1]))
    return diff_evokes

def generate_mean_evokes(evokes):
    import mne
    mean_evokes = []
    for i in range(len(evokes[list(evokes.keys())[0]])):
        mean_evokes.append(mne.combine_evoked(
            [evokes[list(evokes.keys())[0]][i], evokes[list(evokes.keys())[1]][i]], weights='nave'))
    return mean_evokes

def compare_evoke_wave(evokes, chan_name, vlines="auto"):
    import mne
    cond1 = list(evokes.keys())[0]
    cond2 = list(evokes.keys())[1]
    roi = [chan_name]
    # Get evokes
    # Define parameters
    color_dict = {cond1: 'blue', cond2: 'red'}
    linestyle_dict = {cond1: 'solid', cond2: 'dashed'}
    evoke_plot = mne.viz.plot_compare_evokeds(evokes,
                                              vlines=vlines,
                                              legend='lower right',
                                              picks=roi, show_sensors='upper right',
                                              ci=False,
                                              colors=color_dict,
                                              linestyles=linestyle_dict,
                                              title=chan_name + " :  " + cond1 + ' vs. ' + cond2)
    return evoke_plot


def show_difference_wave(evokes_diff, chan_name):
    import mne
    roi = [chan_name]
    difference_wave_plot = mne.viz.plot_compare_evokeds({'diff_evoke': evokes_diff},
                                                        picks=roi,
                                                        show_sensors='upper right',
                                                        combine='mean',
                                                        title=chan_name + "Difference Wave")
    return difference_wave_plot
