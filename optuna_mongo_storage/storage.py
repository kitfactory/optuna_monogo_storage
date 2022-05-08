import abc
import copy
import datetime

from tkinter.messagebox import NO
from typing import Any, FrozenSet
from typing import Callable
from typing import cast
from typing import Container
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union

import optuna
from optuna.distributions import BaseDistribution
from optuna.study._study_direction import StudyDirection
from optuna.study._study_summary import StudySummary
from optuna.trial import FrozenTrial
from optuna.trial import TrialState

from pymongo import MongoClient, DESCENDING, ASCENDING

DEFAULT_STUDY_NAME_PREFIX = "no-name-"

class Trial():
    def __init__(self,number:int,study_id:int,datetime_start=None,datetime_complete=None):
        self.number = number
        self.study_id = study_id
        self.datetime_start = datetime_start
        self.datetime_complete = datetime_complete


class Study():



class OptunaMongoStorage(object, metaclass=abc.ABCMeta):

    """A storage class for storing and loading studies in MongoDB.
    """
    def __init__(self, url:str="mongodb://127.0.0.1:27017", db:str="optuna"):
        self.client = MongoClient(url)
        self.db = self.client[db]

    # Basic study manipulation

    # study collection
    # {
    #   "name": name of study  string
    #   "study_id": id of study int
    #  }
    def create_new_study(self, study_name: Optional[str] = None) -> int:
        """Create a new study from a name.
        If no name is specified, the storage class generates a name.
        The returned study ID is unique among all current and deleted studies.
        Args:
            study_name:
                Name of the new study to create.
        Returns:
            ID of the created study.
        Raises:
            :exc:`optuna.exceptions.DuplicatedStudyError`:
                If a study with the same ``study_name`` already exists.
        """
        # TODO(ytsmiling) Fix RDB storage implementation to ensure unique `study_id`.
        print("Create Study", study_name)

        # duplicate check
        count = self.db.study.count_documents({"study_name": study_name})
        if count != 0:
            raise optuna.exceptions.DuplicatedStudyError(study_name)

        # generate new study id
        cur = self.db.study.find().sort("study_id", DESCENDING).limit(1)
        new_id = -1
        for doc in cur:
            new_id = doc["study_id"]
        new_id += 1
        print( "new study id ", new_id)

        self.db.study.insert_one({"study_id": new_id, "study_name": study_name})
        print( "inserted id", new_id)
        return new_id

    def delete_study(self, study_id: int) -> None:
        """Delete a study.
        Args:
            study_id:
                ID of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError

    def set_study_user_attr(self, study_id: int, key: str, value: Any) -> None:
        """Register a user-defined attribute to a study.
        This method overwrites any existing attribute.
        Args:
            study_id:
                ID of the study.
            key:
                Attribute key.
            value:
                Attribute value. It should be JSON serializable.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError

    def set_study_system_attr(self, study_id: int, key: str, value: Any) -> None:
        """Register an optuna-internal attribute to a study.
        This method overwrites any existing attribute.
        Args:
            study_id:
                ID of the study.
            key:
                Attribute key.
            value:
                Attribute value. It should be JSON serializable.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError



    def set_study_directions(self, study_id: int, directions: Sequence[StudyDirection]) -> None:
        """Register optimization problem directions to a study.
        Args:
            study_id:
                ID of the study.
            directions:
                A sequence of direction whose element is either
                :obj:`~optuna.study.StudyDirection.MAXIMIZE` or
                :obj:`~optuna.study.StudyDirection.MINIMIZE`.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
            :exc:`ValueError`:
                If the directions are already set and the each coordinate of passed ``directions``
                is the opposite direction or :obj:`~optuna.study.StudyDirection.NOT_SET`.
        """
        print("set_study_directions", directions)
        # existance check
        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)
        
        # check all directions are NOT_SET or opposite        
        all_not_set = True
        for d in directions:
            if d != StudyDirection.NOT_SET:
                all_not_set = False
                break
        if all_not_set:
            raise ValueError("All directions are NOT_SET")


        # if all directions are not opposite, then update directions
        serialized_directions = self._serialize_directions(directions)
        study = self.db.study.find_one({"study_id": study_id})
        if "directions" in study:
            opposite = True
            for d,e in zip(serialized_directions, study["directions"]):
                if d + e != StudyDirection.MAXIMIZE + StudyDirection.MINIMIZE:
                    opposite = False
                    break
            if opposite == True:
                raise ValueError("All directions are opposite")
        self.db.study.update_one({"study_id": study_id}, {"$set": {"directions": serialized_directions}})


    # Basic study access
    def get_study_id_from_name(self, study_name: str) -> int:
        """Read the ID of a study.
        Args:
            study_name:
                Name of the study.
        Returns:
            ID of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_name`` exists.
        """

        # existance check
        count = self.db.study.count_documents({"study_name": study_name})
        if count == 0:
            raise KeyError(study_name)
        
        study_id = self.db.study.find_one({"study_name": study_name})["study_id"]
        return study_id


    def get_study_id_from_trial_id(self, trial_id: int) -> int:
        """Read the ID of a study to which a trial belongs.
        Args:
            trial_id:
                ID of the trial.
        Returns:
            ID of the study.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
        """        
        raise NotImplementedError

    def get_study_name_from_id(self, study_id: int) -> str:
        """Read the study name of a study.
        Args:
            study_id:
                ID of the study.
        Returns:
            Name of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        # existance check
        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)

        study_name = self.db.study.find_one({"study_id": study_id})["study_name"]
        return study_name

    def get_study_directions(self, study_id: int) -> List[StudyDirection]:
        """Read whether a study maximizes or minimizes an objective.
        Args:
            study_id:
                ID of a study.
        Returns:
            Optimization directions list of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError


        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)

        serialized_directions = self.db.study.find_one({"study_id": study_id})["directions"]
        directions = self._deserialize_directions(serialized_directions)
        return directions


    def get_study_user_attrs(self, study_id: int) -> Dict[str, Any]:
        """Read the user-defined attributes of a study.
        Args:
            study_id:
                ID of the study.
        Returns:
            Dictionary with the user attributes of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError

        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)

        return self.db.study.find_one({"study_id": study_id})["user_attrs"]


    def get_study_system_attrs(self, study_id: int) -> Dict[str, Any]:
        """Read the optuna-internal attributes of a study.
        Args:
            study_id:
                ID of the study.
        Returns:
            Dictionary with the optuna-internal attributes of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        raise NotImplementedError

        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)

        return self.db.study.find_one({"study_id": study_id})["system_attrs"]

    def get_all_study_summaries(self, include_best_trial: bool) -> List[StudySummary]:
        """Read a list of :class:`~optuna.study.StudySummary` objects.
        Args:
            include_best_trial:
                If :obj:`True`, :obj:`~optuna.study.StudySummary` objects have the best trials in
                the ``best_trial`` attribute. Otherwise, ``best_trial`` is :obj:`None`.
        Returns:
            A list of :class:`~optuna.study.StudySummary` objects.
        """
        raise NotImplementedError

    # Basic trial manipulation

    def create_new_trial(self, study_id: int, template_trial: Optional[FrozenTrial] = None) -> int:
        """Create and add a new trial to a study.
        The returned trial ID is unique among all current and deleted trials.
        Args:
            study_id:
                ID of the study.
            template_trial:
                Template :class:`~optuna.trial.FronzenTrial` with default user-attributes,
                system-attributes, intermediate-values, and a state.
        Returns:
            ID of the created trial.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """

        if template_trial is not None:
            print("template trial is supported.")
            raise NotImplementedError

        # existance check
        count = self.db.study.count_documents({"study_id": study_id})
        if count == 0:
            raise KeyError(study_id)

        # generate new trial id
        cur = self.db.trial.find().sort("trial_id", DESCENDING).limit(1)
        new_id = -1
        for doc in cur:
            new_id = doc["trial_id"]
        new_id += 1
        print( "new trial id ", new_id)

        trial = self._create_new_trial(study_id,template_trial)
        self.db.trial.insert_one({"study_id": study_id, "trial_id": new_id})
        return new_id


    def _get_prepared_new_trial(
        self, study_id: int, template_trial: Optional[FrozenTrial]
    ) -> Trial:
        if template_trial is None:
            trial = Trial(
                study_id=study_id,
                number=None,
                state=TrialState.RUNNING,
                datetime_start=datetime.now(),
            )
        else:
            # Because only `RUNNING` trials can be updated,
            # we temporarily set the state of the new trial to `RUNNING`.
            # After all fields of the trial have been updated,
            # the state is set to `template_trial.state`.
            temp_state = TrialState.RUNNING

            trial = Trial(
                study_id=study_id,
                number=None,
                state=temp_state,
                datetime_start=template_trial.datetime_start,
                datetime_complete=template_trial.datetime_complete,
            )

            if template_trial.values is not None and len(template_trial.values) > 1:
                for objective, value in enumerate(template_trial.values):
                    self._set_trial_value_without_commit(session, trial.trial_id, objective, value)
            elif template_trial.value is not None:
                self._set_trial_value_without_commit(
                    session, trial.trial_id, 0, template_trial.value
                )

            for param_name, param_value in template_trial.params.items():
                distribution = template_trial.distributions[param_name]
                param_value_in_internal_repr = distribution.to_internal_repr(param_value)
                self._set_trial_param_without_commit(
                    session, trial.trial_id, param_name, param_value_in_internal_repr, distribution
                )

            for key, value in template_trial.user_attrs.items():
                self._set_trial_user_attr_without_commit(session, trial.trial_id, key, value)

            for key, value in template_trial.system_attrs.items():
                self._set_trial_system_attr_without_commit(session, trial.trial_id, key, value)

            for step, intermediate_value in template_trial.intermediate_values.items():
                self._set_trial_intermediate_value_without_commit(
                    session, trial.trial_id, step, intermediate_value
                )

            trial.state = template_trial.state

        trial.number = trial.count_past_trials(session)
        session.add(trial)

        return trial



    def _create_new_trial(
        self, study_id: int, template_trial: Optional[FrozenTrial] = None
    ) -> FrozenTrial:
        """Create a new trial and returns its trial_id and a :class:`~optuna.trial.FrozenTrial`.

        Args:
            study_id:
                Study id.
            template_trial:
                A :class:`~optuna.trial.FrozenTrial` with default values for trial attributes.

        Returns:
            A :class:`~optuna.trial.FrozenTrial` instance.

        """
        trial_obj = self._get_prepared_new_trial(study_id, template_trial)

        if template_trial:
            frozen = copy.deepcopy(template_trial)
            frozen.number = trial.number
            frozen.datetime_start = trial.datetime_start
            frozen._trial_id = trial.trial_id
        else:
            frozen = FrozenTrial(
                number=trial.number,
                state=trial.state,
                value=None,
                values=None,
                datetime_start=trial.datetime_start,
                datetime_complete=None,
                params={},
                distributions={},
                user_attrs={},
                system_attrs={},
                intermediate_values={},
                trial_id=trial.trial_id,
            )

        return frozen








    def set_trial_param(
        self,
        trial_id: int,
        param_name: str,
        param_value_internal: float,
        distribution: BaseDistribution,
    ) -> None:
        """Set a parameter to a trial.
        Args:
            trial_id:
                ID of the trial.
            param_name:
                Name of the parameter.
            param_value_internal:
                Internal representation of the parameter value.
            distribution:
                Sampled distribution of the parameter.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
            :exc:`RuntimeError`:
                If the trial is already finished.
        """
        raise NotImplementedError

    def get_trial_id_from_study_id_trial_number(self, study_id: int, trial_number: int) -> int:
        """Read the trial ID of a trial.
        Args:
            study_id:
                ID of the study.
            trial_number:
                Number of the trial.
        Returns:
            ID of the trial.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``study_id`` and ``trial_number`` exists.
        """
        raise NotImplementedError

    def get_trial_number_from_id(self, trial_id: int) -> int:
        """Read the trial number of a trial.
        .. note::
            The trial number is only unique within a study, and is sequential.
        Args:
            trial_id:
                ID of the trial.
        Returns:
            Number of the trial.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
        """
        return self.get_trial(trial_id).number

    def get_trial_param(self, trial_id: int, param_name: str) -> float:
        """Read the parameter of a trial.
        Args:
            trial_id:
                ID of the trial.
            param_name:
                Name of the parameter.
        Returns:
            Internal representation of the parameter.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
                If no such parameter exists.
        """
        trial = self.get_trial(trial_id)
        return trial.distributions[param_name].to_internal_repr(trial.params[param_name])

    def set_trial_state_values(
        self, trial_id: int, state: TrialState, values: Optional[Sequence[float]] = None
    ) -> bool:
        """Update the state and values of a trial.
        Set return values of an objective function to values argument.
        If values argument is not :obj:`None`, this method overwrites any existing trial values.
        Args:
            trial_id:
                ID of the trial.
            state:
                New state of the trial.
            values:
                Values of the objective function.
        Returns:
            :obj:`True` if the state is successfully updated.
            :obj:`False` if the state is kept the same.
            The latter happens when this method tries to update the state of
            :obj:`~optuna.trial.TrialState.RUNNING` trial to
            :obj:`~optuna.trial.TrialState.RUNNING`.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
            :exc:`RuntimeError`:
                If the trial is already finished.
        """
        raise NotImplementedError

    def set_trial_intermediate_value(
        self, trial_id: int, step: int, intermediate_value: float
    ) -> None:
        """Report an intermediate value of an objective function.
        This method overwrites any existing intermediate value associated with the given step.
        Args:
            trial_id:
                ID of the trial.
            step:
                Step of the trial (e.g., the epoch when training a neural network).
            intermediate_value:
                Intermediate value corresponding to the step.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
            :exc:`RuntimeError`:
                If the trial is already finished.
        """
        raise NotImplementedError

    def set_trial_user_attr(self, trial_id: int, key: str, value: Any) -> None:
        """Set a user-defined attribute to a trial.
        This method overwrites any existing attribute.
        Args:
            trial_id:
                ID of the trial.
            key:
                Attribute key.
            value:
                Attribute value. It should be JSON serializable.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
            :exc:`RuntimeError`:
                If the trial is already finished.
        """
        raise NotImplementedError

    def set_trial_system_attr(self, trial_id: int, key: str, value: Any) -> None:
        """Set an optuna-internal attribute to a trial.
        This method overwrites any existing attribute.
        Args:
            trial_id:
                ID of the trial.
            key:
                Attribute key.
            value:
                Attribute value. It should be JSON serializable.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
            :exc:`RuntimeError`:
                If the trial is already finished.
        """
        raise NotImplementedError

    # Basic trial access
    def get_trial(self, trial_id: int) -> FrozenTrial:
        """Read a trial.
        Args:
            trial_id:
                ID of the trial.
        Returns:
            Trial with a matching trial ID.
        Raises:
            :exc:`KeyError`:
                If no trial with the matching ``trial_id`` exists.
        """

        
        # existance check
        count = self.db.trial.count_documents({"trial_id": trial_id})
        if count == 0:
            raise KeyError(trial_id)

        trial_doc = self.db.trial.find_one({"trial_id": trial_id})
        trial =(trial_id, trial_doc["study_id"], trial_doc["number"], trial_doc["state"], trial_doc["params"], trial_doc["distributions"], trial_doc["user_attrs"], trial_doc["system_attrs"], trial_doc["intermediate_values"], trial_doc["date_created"], trial_doc["date_updated"], trial_doc["date_completed"], trial_doc["date_terminated"])

        return trial

    """
        Trial
        number:->int
            Unique and consecutive number of :class:`~optuna.trial.Trial` for each
            :class:`~optuna.study.Study`. Note that this field uses zero-based numbering.
        state: (RUNNING,WAITING,COMPLETE,PRUNED,FAIL)
        value:
            Objective value of the :class:`~optuna.trial.Trial`.
        values:
            Sequence of objective values of the :class:`~optuna.trial.Trial`.
            The length is greater than 1 if the problem is multi-objective optimization.
        datetime_start:
            Datetime where the :class:`~optuna.trial.Trial` started.
        datetime_complete:
            Datetime where the :class:`~optuna.trial.Trial` finished.
        params:
            Dictionary that contains suggested parameters.
        user_attrs:
            Dictionary that contains the attributes of the :class:`~optuna.trial.Trial` set with
            :func:`optuna.trial.Trial.set_user_attr`.
        intermediate_values:
            Intermediate objective values set with :func:`optuna.trial.Trial.report`.
    """

    def get_all_trials(
        self,
        study_id: int,
        deepcopy: bool = True,
        states: Optional[Container[TrialState]] = None,
    ) -> List[FrozenTrial]:
        """Read all trials in a study.
        Args:
            study_id:
                ID of the study.
            deepcopy:
                Whether to copy the list of trials before returning.
                Set to :obj:`True` if you intend to update the list or elements of the list.
            states:
                Trial states to filter on. If :obj:`None`, include all states.
        Returns:
            List of trials in the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """

        studies = self.db.study.count_documents({"study_id":study_id})
        if studies == 0:
            raise KeyError("No study with the matching study_id exists.")

        ret = []
        for trial in self.db.trial.find({"study_id":study_id}):
            if states is None or trial["state"] in states:
                ret.append(FrozenTrial(trial, deepcopy))        
        return ret

    # def get_n_trials(
    #     self, study_id: int, state: Optional[Union[Tuple[TrialState, ...], TrialState]] = None
    # ) -> int:
    #     """Count the number of trials in a study.
    #     Args:
    #         study_id:
    #             ID of the study.
    #         state:
    #             Trial states to filter on. If :obj:`None`, include all states.
    #     Returns:
    #         Number of trials in the study.
    #     Raises:
    #         :exc:`KeyError`:
    #             If no study with the matching ``study_id`` exists.
    #     """
    #     # TODO(hvy): Align the name and the behavior or the `state` parameter with
    #     # `get_all_trials`'s `states`.
    #     if isinstance(state, TrialState):
    #         state = (state,)
    #     return len(self.get_all_trials(study_id, deepcopy=False, states=state))

    # def get_best_trial(self, study_id: int) -> FrozenTrial:
    #     """Return the trial with the best value in a study.
    #     This method is valid only during single-objective optimization.
    #     Args:
    #         study_id:
    #             ID of the study.
    #     Returns:
    #         The trial with the best objective value among all finished trials in the study.
    #     Raises:
    #         :exc:`KeyError`:
    #             If no study with the matching ``study_id`` exists.
    #         :exc:`RuntimeError`:
    #             If the study has more than one direction.
    #         :exc:`ValueError`:
    #             If no trials have been completed.
    #     """
    #     all_trials = self.get_all_trials(study_id, deepcopy=False)
    #     all_trials = [t for t in all_trials if t.state is TrialState.COMPLETE]

    #     if len(all_trials) == 0:
    #         raise ValueError("No trials are completed yet.")

    #     directions = self.get_study_directions(study_id)
    #     if len(directions) > 1:
    #         raise RuntimeError(
    #             "Best trial can be obtained only for single-objective optimization."
    #         )
    #     direction = directions[0]

    #     if direction == StudyDirection.MAXIMIZE:
    #         best_trial = max(all_trials, key=lambda t: cast(float, t.value))
    #     else:
    #         best_trial = min(all_trials, key=lambda t: cast(float, t.value))

    #     return best_trial

    # def get_trial_params(self, trial_id: int) -> Dict[str, Any]:
    #     """Read the parameter dictionary of a trial.
    #     Args:
    #         trial_id:
    #             ID of the trial.
    #     Returns:
    #         Dictionary of a parameters. Keys are parameter names and values are internal
    #         representations of the parameter values.
    #     Raises:
    #         :exc:`KeyError`:
    #             If no trial with the matching ``trial_id`` exists.
    #     """
    #     return self.get_trial(trial_id).params

    # def get_trial_user_attrs(self, trial_id: int) -> Dict[str, Any]:
    #     """Read the user-defined attributes of a trial.
    #     Args:
    #         trial_id:
    #             ID of the trial.
    #     Returns:
    #         Dictionary with the user-defined attributes of the trial.
    #     Raises:
    #         :exc:`KeyError`:
    #             If no trial with the matching ``trial_id`` exists.
    #     """
    #     return self.get_trial(trial_id).user_attrs

    # def get_trial_system_attrs(self, trial_id: int) -> Dict[str, Any]:
    #     """Read the optuna-internal attributes of a trial.
    #     Args:
    #         trial_id:
    #             ID of the trial.
    #     Returns:
    #         Dictionary with the optuna-internal attributes of the trial.
    #     Raises:
    #         :exc:`KeyError`:
    #             If no trial with the matching ``trial_id`` exists.
    #     """
    #     return self.get_trial(trial_id).system_attrs

    def read_trials_from_remote_storage(self, study_id: int) -> None:
        """Make an internal cache of trials up-to-date.
        Args:
            study_id:
                ID of the study.
        Raises:
            :exc:`KeyError`:
                If no study with the matching ``study_id`` exists.
        """
        print("read_trials_from_remote_storage")
        # raise NotImplementedError

    # def remove_session(self) -> None:
    #     """Clean up all connections to a database."""
    #     pass

    # def check_trial_is_updatable(self, trial_id: int, trial_state: TrialState) -> None:
    #     """Check whether a trial state is updatable.
    #     Args:
    #         trial_id:
    #             ID of the trial.
    #             Only used for an error message.
    #         trial_state:
    #             Trial state to check.
    #     Raises:
    #         :exc:`RuntimeError`:
    #             If the trial is already finished.
    #     """
    #     if trial_state.is_finished():
    #         trial = self.get_trial(trial_id)
    #         raise RuntimeError(
    #             "Trial#{} has already finished and can not be updated.".format(trial.number)
    #         )

    # def record_heartbeat(self, trial_id: int) -> None:
    #     """Record the heartbeat of the trial.
    #     Args:
    #         trial_id:
    #             ID of the trial.
    #     """
    #     pass

    # def _get_stale_trial_ids(self, study_id: int) -> List[int]:
    #     """Get the stale trial ids of the study.
    #     Args:
    #         study_id:
    #             ID of the study.
    #     Returns:
    #         List of IDs of trials whose heartbeat has not been updated for a long time.
    #     """
    #     return []

    def is_heartbeat_enabled(self) -> bool:
        """Check whether the storage enables the heartbeat.
        Returns:
            :obj:`True` if the storage supports the heartbeat and the return value of
            :meth:`~optuna.storages.BaseStorage.get_heartbeat_interval` is an integer,
            otherwise :obj:`False`.
        """
        return self._is_heartbeat_supported() and self.get_heartbeat_interval() is not None

    def _is_heartbeat_supported(self) -> bool:
        return False

    def get_heartbeat_interval(self) -> Optional[int]:
        """Get the heartbeat interval if it is set.
        Returns:
            The heartbeat interval if it is set, otherwise :obj:`None`.
        """
        return None

    def get_failed_trial_callback(self) -> Optional[Callable[["optuna.Study", FrozenTrial], None]]:
        """Get the failed trial callback function.
        Returns:
            The failed trial callback function if it is set, otherwise :obj:`None`.
        """
        return None
    
    def _serialize_directions(self, directions: Sequence[StudyDirection]):
        ret = []
        for d in directions:
            ret.append(d.value)
        return ret    

    def _deserialize_directions(self, directions: Sequence[int]):
        ret = []
        for d in directions:
            ret.append(StudyDirection(d))
        return ret

    def _serialize_trial(self, trial:FrozenTrial):
        ret = {}

        if trial.number is not None:
            ret['number'] = trial.number

        if trial.state is not None:
            ret['state'] = trial.state.value

        if trial.value is not None:
            ret['value'] = trial.value
        
        if trial.values is not None:
            ret['values'] = trial.values

        if trial.datetime_start is not None:
             ret['datetime_start'] = trial.datetime_start.timestamp()
        
        if trial.datetime_complete is not None:
            ret['datetime_complete'] = trial.datetime_complete.timestamp()

        if trial.params is not None:
            ret['params'] = trial.params

        if trial.user_attrs is not None:
            ret['user_attrs'] = trial.user_attrs

        return ret


    def _deserialize_trial(self, trial):
        state = TrialState(trial.state)
        datetime_start = trial.datetime_start
        ret = FrozenTrial(number, state, value, datetime_start,datatime_complete,params,distribution,user_attrs,system_attrs,intermediate_values,trial_id,values)
        return ret
