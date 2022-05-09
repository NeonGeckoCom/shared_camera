from setuptools import setup

setup(
    name='shared_camera',
    version='0.1',
    packages=['shared_camera'],
    url='https://github.com/NeonJarbas/shared_camera',
    author='Neongecko',
    author_email='developers@neon.ai',
    license='BSD-3.0',
    include_package_data=True,
    install_requires=["imutils>=0.5.3",
                      "opencv_python>=4.4.0.46",
                      "imagezmq>=1.1.1"],
    author_email='jarbasai@mailfence.com',
    description='inter process camera interface'
)
