from faker import Faker

fake = Faker()


def test_example():
    num1 = fake.pyint()
    num2 = fake.pyint()
    assert num1 != num2
