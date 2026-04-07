
import pickle

label_dict = {
    1: [{"supercategory": "none", "id": 1, "name": "car"}],

   2:[{"supercategory": "none", "id": 2, "name": "car_num"}]
}

with open('car.pkl', 'wb') as f:
    pickle.dump(label_dict, f)

with open('car.pkl', 'rb') as f:
    label_map = pickle.load(f)
    print(label_map)