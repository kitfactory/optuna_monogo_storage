import unittest
import datetime
import optuna
from optuna_mongo_storage.storage import OptunaMongoStorage

# Define an objective function to be minimized.
def objective(trial):
    x = trial.suggest_float('suggest', 1e-10, 1e10, log=True)
    ret = x * x
    return x  # An objective value linked with the Trial object.

def test_main():
    date_str = datetime.datetime.now()
    storage = OptunaMongoStorage()
    study = optuna.create_study(storage=storage,study_name="test "+ str(date_str))  # Create a new study.
    study.optimize(objective, n_trials=100)  # Invoke optimization of the objective function.


# class TestOptunaStorage(unittest.TestCase):

#     def test_study(self):
#         test_main()
#         self.assertTrue(True)

if __name__ == '__main__':
    test_main()
    # unittest.main()